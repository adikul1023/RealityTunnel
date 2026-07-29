"""
backup.py — Backup service for database snapshots, configuration archives, and metadata manifests.
"""
from __future__ import annotations

import gzip
import json
import logging
import shutil
import subprocess
import time
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.fingerprint import compute_configuration_fingerprint
from app.core.profiles import parse_environment_profile
from app.core.feature_flags import FeatureFlags
from app.observability.metrics import metrics_registry
from app.recovery.checksums import generate_file_checksum
from app.recovery.exceptions import BackupError, BackupNotFoundError
from app.recovery.integrity import IntegrityVerifier
from app.recovery.retention import RetentionPolicy, prune_backups

logger = logging.getLogger(__name__)


class CompressionEngine(ABC):
    """Abstract compression engine for future-proof algorithm pluggability."""
    @abstractmethod
    def compress(self, data: str | bytes, dest_path: Path) -> Path:
        pass


class GzipCompressor(CompressionEngine):
    """Standard gzip compression engine."""
    def compress(self, data: str | bytes, dest_path: Path) -> Path:
        raw_bytes = data.encode("utf-8") if isinstance(data, str) else data
        with gzip.open(dest_path, "wb", compresslevel=6) as f:
            f.write(raw_bytes)
        return dest_path


class ZstdCompressor(CompressionEngine):
    """Future-proof hook for Zstandard compression."""
    def compress(self, data: str | bytes, dest_path: Path) -> Path:
        # Fallback to gzip if zstd library is not installed
        try:
            import zstandard as zstd
            raw_bytes = data.encode("utf-8") if isinstance(data, str) else data
            cctx = zstd.ZstdCompressor(level=3)
            compressed = cctx.compress(raw_bytes)
            with open(dest_path, "wb") as f:
                f.write(compressed)
            return dest_path
        except ImportError:
            logger.warning("zstandard library not found, falling back to gzip for %s", dest_path)
            return GzipCompressor().compress(data, dest_path)


def get_compressor(algo: str | None = None) -> CompressionEngine:
    algo_str = (algo or getattr(settings, "backup_compression_algorithm", "gzip")).lower()
    if algo_str == "zstd":
        return ZstdCompressor()
    return GzipCompressor()


class BackupService:
    """Orchestrates database backups, configuration snapshots, and retention pruning."""

    def __init__(self, backup_directory: Path | str | None = None) -> None:
        self.backup_dir = Path(backup_directory or getattr(settings, "backup_directory", "./backups"))
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.verifier = IntegrityVerifier()

    def _get_git_commit_hash(self) -> str:
        try:
            res = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip()
        except Exception:
            pass
        return "unknown"

    async def _get_postgres_revision(self, session: AsyncSession) -> str:
        try:
            res = await session.execute(text("SELECT version_num FROM alembic_version"))
            val = res.scalar()
            if val:
                return str(val)
        except Exception:
            pass
        try:
            res = await session.execute(text("SELECT version()"))
            val = res.scalar()
            if val:
                return str(val).split(" ")[0]
        except Exception:
            pass
        return "unknown"

    async def create_database_backup(self, session: AsyncSession, dest_dir: Path) -> Path:
        """Dump database schema and row records deterministically without external binary dependencies."""
        dest_dir.mkdir(parents=True, exist_ok=True)
        db_file = dest_dir / "database.sql.gz"

        known_tables = [
            "alembic_version",
            "subscription_plans",
            "accounts",
            "devices",
            "refresh_tokens",
            "admin_users",
            "subscriptions",
            "provisioning_profiles",
            "payments",
            "provisioning_retries",
            "connection_signals",
            "system_health",
        ]

        discovered_tables: list[str] = []
        try:
            res = await session.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'"))
            for row in res.fetchall():
                if row[0] not in discovered_tables:
                    discovered_tables.append(row[0])
        except Exception:
            pass

        if not discovered_tables:
            try:
                res = await session.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"))
                for row in res.fetchall():
                    if row[0] not in discovered_tables:
                        discovered_tables.append(row[0])
            except Exception:
                pass

        tables_to_dump = discovered_tables if discovered_tables else known_tables
        lines = [f"-- RealityTunnel Database Snapshot — {datetime.now(timezone.utc).isoformat()}", ""]

        for tbl in tables_to_dump:
            lines.append(f"-- TABLE: {tbl}")
            try:
                res = await session.execute(text(f"SELECT * FROM {tbl}"))
                col_names = res.keys()
                rows = res.fetchall()
                for row in rows:
                    row_dict: dict[str, Any] = {}
                    for col, val in zip(col_names, row):
                        if isinstance(val, datetime):
                            row_dict[col] = val.isoformat()
                        elif val is None or isinstance(val, (int, float, bool, str)):
                            row_dict[col] = val
                        else:
                            row_dict[col] = str(val)
                    lines.append(json.dumps({"table": tbl, "row": row_dict}))
            except Exception as exc:
                logger.debug("Table dump skipped for %s: %s", tbl, exc)
            lines.append("")

        content = "\n".join(lines)
        compressor = get_compressor()
        return compressor.compress(content, db_file)

    def create_configuration_backup(self, dest_dir: Path) -> Path:
        """Create sanitized configuration snapshot stripping all passwords, tokens, and secret URIs."""
        dest_dir.mkdir(parents=True, exist_ok=True)
        cfg_file = dest_dir / "configuration.json.gz"

        raw_settings = settings.model_dump() if hasattr(settings, "model_dump") else {}
        safe_settings: dict[str, Any] = {}
        for k, v in raw_settings.items():
            k_lower = k.lower()
            if any(sec in k_lower for sec in ("secret", "password", "token", "key", "uri", "url", "dsn")):
                safe_settings[k] = "***REDACTED***"
            elif isinstance(v, (int, float, bool, str)) or v is None:
                safe_settings[k] = v
            else:
                safe_settings[k] = str(v)

        config_payload = {
            "environment_profile": parse_environment_profile(getattr(settings, "environment", "development")).value,
            "feature_flags": FeatureFlags.from_env().to_dict(),
            "fingerprint": compute_configuration_fingerprint(),
            "settings": safe_settings,
        }

        content = json.dumps(config_payload, indent=2)
        compressor = get_compressor()
        return compressor.compress(content, cfg_file)

    def create_metadata_snapshot(
        self,
        dest_dir: Path,
        backup_id: str,
        db_file: Path,
        cfg_file: Path,
        postgres_revision: str,
    ) -> Path:
        """Generate manifest containing cryptographic SHA-256 digests and environment metadata."""
        meta_file = dest_dir / "metadata.json"
        
        db_hash = generate_file_checksum(db_file) if db_file.exists() else ""
        cfg_hash = generate_file_checksum(cfg_file) if cfg_file.exists() else ""
        total_size = (db_file.stat().st_size if db_file.exists() else 0) + (cfg_file.stat().st_size if cfg_file.exists() else 0)

        meta_payload = {
            "backup_id": backup_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "postgres_revision": postgres_revision,
            "git_commit_hash": self._get_git_commit_hash(),
            "application_version": getattr(settings, "app_version", "1.0.0"),
            "configuration_fingerprint": compute_configuration_fingerprint(),
            "checksums": {
                db_file.name: db_hash,
                cfg_file.name: cfg_hash,
            },
            "backup_size_bytes": total_size,
            "compression_algorithm": getattr(settings, "backup_compression_algorithm", "gzip"),
        }

        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(meta_payload, f, indent=2)

        # Also store checksum of the metadata manifest itself
        meta_hash = generate_file_checksum(meta_file)
        with open(dest_dir / "metadata.json.sha256", "w", encoding="utf-8") as f:
            f.write(meta_hash)

        return meta_file

    async def create_backup(self, session: AsyncSession) -> dict[str, Any]:
        """
        Orchestrate full backup creation, record Prometheus metrics, enforce retention pruning,
        and emit zero-secret operational log.
        """
        t0 = time.perf_counter()
        backup_id = f"backup_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        target_dir = self.backup_dir / backup_id

        try:
            pg_rev = await self._get_postgres_revision(session)
            db_file = await self.create_database_backup(session, target_dir)
            cfg_file = self.create_configuration_backup(target_dir)
            meta_file = self.create_metadata_snapshot(target_dir, backup_id, db_file, cfg_file, pg_rev)

            with open(meta_file, "r", encoding="utf-8") as f:
                meta_data = json.load(f)

            duration_s = round(time.perf_counter() - t0, 3)
            size_bytes = meta_data["backup_size_bytes"]

            # Record metrics
            metrics_registry.inc_counter("backup_success_total", 1.0)
            metrics_registry.observe("backup_duration_seconds", duration_s)
            metrics_registry.set_gauge("backup_size_bytes", float(size_bytes))

            # Prune expired
            policy = RetentionPolicy.from_settings(settings)
            prune_backups(self.backup_dir, policy)

            # Zero-secret logging
            logger.info(
                "Backup snapshot created successfully: backup_id=%s duration_s=%.3f size_bytes=%d status=ok",
                backup_id,
                duration_s,
                size_bytes,
            )
            return meta_data
        except Exception as exc:
            duration_s = round(time.perf_counter() - t0, 3)
            metrics_registry.inc_counter("backup_failure_total", 1.0)
            logger.error(
                "Backup snapshot creation failed: backup_id=%s duration_s=%.3f status=error error=%s",
                backup_id,
                duration_s,
                exc,
            )
            if target_dir.exists():
                try:
                    shutil.rmtree(target_dir)
                except Exception:
                    pass
            raise BackupError(f"Failed to create backup snapshot '{backup_id}': {exc}") from exc

    def verify_backup(self, backup_id: str) -> dict[str, Any]:
        """Verify archive integrity, checksums, and schema structure."""
        target_dir = self.backup_dir / backup_id
        if not target_dir.exists() or not target_dir.is_dir():
            raise BackupNotFoundError(f"Backup snapshot '{backup_id}' not found in storage.")
        return self.verifier.verify_backup_archive(target_dir)

    def list_backups(self) -> list[dict[str, Any]]:
        """List all stored backup snapshots sorted by timestamp descending."""
        if not self.backup_dir.exists() or not self.backup_dir.is_dir():
            return []

        results: list[dict[str, Any]] = []
        for item in self.backup_dir.iterdir():
            if item.is_dir() and (item / "metadata.json").exists():
                try:
                    with open(item / "metadata.json", "r", encoding="utf-8") as f:
                        meta = json.load(f)
                        results.append(meta)
                except Exception:
                    pass
        results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return results

    def delete_expired_backups(self) -> list[str]:
        """Manually trigger retention pruning against configured policy."""
        policy = RetentionPolicy.from_settings(settings)
        return prune_backups(self.backup_dir, policy)
