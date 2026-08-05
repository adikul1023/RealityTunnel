"""
profiler.py — Automatic latency profiling, percentile summaries, and resource utilization monitoring.
"""
import asyncio
import logging
import math
import os
import threading
import time
from collections import defaultdict, deque
from typing import Any

from app.config import settings
from app.observability.metrics import metrics_registry
from app.performance.exceptions import ProfilingError

logger = logging.getLogger(__name__)

try:
    import psutil # type: ignore[import-untyped]
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


class PerformanceProfiler:
    """
    Tracks latency samples across query, endpoint, service, and background job categories.
    Computes P50, P90, P95, and P99 latency percentiles and monitors system resources.
    """

    def __init__(self, max_samples: int = 5000) -> None:
        self.max_samples = max_samples
        self._samples: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=self.max_samples))
        self._lock = threading.Lock()
        self._start_time = time.time()

    def record_latency(self, category: str, duration_seconds: float) -> None:
        """Record a duration sample (in seconds) under a specific category."""
        if not settings.profiler_enabled or duration_seconds < 0:
            return
        with self._lock:
            self._samples[category].append(float(duration_seconds))

        # Update associated Prometheus summary metric
        if category == "query":
            metrics_registry.observe("db_query_seconds", duration_seconds)
        elif category == "endpoint":
            metrics_registry.observe("endpoint_latency_seconds", duration_seconds)
        elif category == "job":
            metrics_registry.observe("scheduler_duration_seconds", duration_seconds)

    def calculate_percentiles(self, samples: list[float]) -> dict[str, float]:
        """Compute P50, P90, P95, and P99 percentiles from a sequence of duration samples (in ms)."""
        if not samples:
            return {"p50": 0.0, "p90": 0.0, "p95": 0.0, "p99": 0.0, "avg": 0.0, "count": 0}

        sorted_samples = sorted(s * 1000.0 for s in samples)  # Convert to ms
        n = len(sorted_samples)
        avg_ms = sum(sorted_samples) / n

        def _get_pct(pct: float) -> float:
            idx = math.ceil((pct / 100.0) * n) - 1
            idx = max(0, min(n - 1, idx))
            return round(sorted_samples[idx], 2)

        return {
            "p50": _get_pct(50.0),
            "p90": _get_pct(90.0),
            "p95": _get_pct(95.0),
            "p99": _get_pct(99.0),
            "avg": round(avg_ms, 2),
            "count": n,
        }

    def get_category_percentiles(self, category: str) -> dict[str, float]:
        with self._lock:
            samples = list(self._samples.get(category, []))
        return self.calculate_percentiles(samples)

    def get_all_percentiles(self) -> dict[str, dict[str, float]]:
        with self._lock:
            categories = list(self._samples.keys())
        return {cat: self.get_category_percentiles(cat) for cat in categories}

    def get_resource_usage(self) -> dict[str, Any]:
        """Collect real-time system resource utilization statistics."""
        try:
            # CPU and Memory
            if PSUTIL_AVAILABLE:
                proc = psutil.Process(os.getpid())
                mem_bytes = proc.memory_info().rss
                cpu_pct = proc.cpu_percent(interval=None)
            else:
                mem_bytes = 64 * 1024 * 1024  # 64 MB fallback approximation
                cpu_pct = 5.0

            # Asyncio tasks
            try:
                active_tasks = len(asyncio.all_tasks())
            except RuntimeError:
                active_tasks = 0

            # DB Connections
            from app.performance.pooling import get_pool_status
            pool_stats = get_pool_status()

            # Update Prometheus gauges
            metrics_registry.set_gauge("memory_usage_bytes", float(mem_bytes))
            metrics_registry.set_gauge("cpu_usage_percent", float(cpu_pct))

            return {
                "cpu_usage_percent": round(cpu_pct, 2),
                "memory_usage_bytes": mem_bytes,
                "memory_usage_mb": round(mem_bytes / (1024 * 1024), 2),
                "active_asyncio_tasks": active_tasks,
                "db_pool_usage": pool_stats.get("checked_out", 0),
                "db_pool_capacity": pool_stats.get("total_capacity", 0),
                "uptime_seconds": round(time.time() - self._start_time, 2),
            }
        except Exception as exc:
            logger.error(f"Error collecting resource usage: {exc}")
            return {
                "cpu_usage_percent": 0.0,
                "memory_usage_bytes": 0,
                "memory_usage_mb": 0.0,
                "active_asyncio_tasks": 0,
                "db_pool_usage": 0,
                "db_pool_capacity": 0,
                "error": str(exc),
            }

    def reset(self) -> None:
        """Clear recorded latency samples."""
        with self._lock:
            self._samples.clear()


# Global profiler instance
profiler = PerformanceProfiler()
