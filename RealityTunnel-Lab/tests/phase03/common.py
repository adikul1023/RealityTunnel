"""
common.py — shared utilities for Phase 0.3 Marzban runtime validation.

Uses only Python stdlib. Tested on Python 3.8+.
Self-signed cert accepted via a no-verify SSL context.
"""

from __future__ import annotations

import base64
import json
import os
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────

_HERE = Path(__file__).parent
LAB_ROOT = _HERE.parent.parent  # RealityTunnel-Lab/
COMPOSE_DIR = str(LAB_ROOT / "compose")
DB_PATH = LAB_ROOT / "data" / "marzban" / "db.sqlite3"
ENV_PATH = LAB_ROOT / "compose" / ".env"
RESULTS_DIR = _HERE / "results"
RESULTS_DIR.mkdir(exist_ok=True)

# ── Config ─────────────────────────────────────────────────────────────────

MARZBAN_URL = "https://localhost:8000"
ADMIN_USER = "admin"
ADMIN_PASS = "labtest123"

# ── SSL ────────────────────────────────────────────────────────────────────

_SSL = ssl.create_default_context()
_SSL.check_hostname = False
_SSL.verify_mode = ssl.CERT_NONE

# ── Console formatting ─────────────────────────────────────────────────────

_G = "\033[92m"
_R = "\033[91m"
_Y = "\033[93m"
_C = "\033[96m"
_B = "\033[1m"
_X = "\033[0m"


def section(title: str) -> None:
    print(f"\n{_B}{_C}{'─' * 62}{_X}")
    print(f"{_B}{_C}  {title}{_X}")
    print(f"{_B}{_C}{'─' * 62}{_X}")


def ok(msg: str) -> None:
    print(f"  {_G}✓{_X}  {msg}")


def fail(msg: str) -> None:
    print(f"  {_R}✗{_X}  {msg}")


def note(msg: str) -> None:
    print(f"  {_Y}→{_X}  {msg}")


def step(msg: str) -> None:
    print(f"\n  {_B}»{_X} {msg}")


def row(k: str, v) -> None:
    print(f"     {_Y}{k:<35}{_X}{v}")


def warn(msg: str) -> None:
    print(f"\n  {_Y}⚠  {msg}{_X}")


def client_required(msg: str) -> None:
    print(f"\n  {_B}{_Y}[CLIENT REQUIRED]{_X} {msg}")


# ── MarzbanClient ──────────────────────────────────────────────────────────


class MarzbanClient:
    def __init__(
        self,
        url: str = MARZBAN_URL,
        username: str = ADMIN_USER,
        password: str = ADMIN_PASS,
    ) -> None:
        self.url = url
        self.token = ""
        self.auth_at = 0.0
        self._login(username, password)

    # ── auth ───────────────────────────────────────────────────────────────

    def _login(self, username: str, password: str) -> None:
        payload = urllib.parse.urlencode(
            {"username": username, "password": password}
        ).encode()
        req = urllib.request.Request(
            f"{self.url}/api/admin/token",
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        status, body = self._raw(req)
        if status != 200:
            raise RuntimeError(f"Login failed {status}: {body}")
        self.token = body["access_token"]
        self.auth_at = time.time()

    def _hdrs(self) -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    # ── low-level request ──────────────────────────────────────────────────

    def _raw(self, req: urllib.request.Request) -> tuple[int, object]:
        try:
            with urllib.request.urlopen(req, context=_SSL) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            raw = e.read().decode()
            try:
                return e.code, json.loads(raw)
            except Exception:
                return e.code, raw

    def _req(self, method: str, path: str, body=None) -> tuple[int, object]:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            f"{self.url}{path}",
            data=data,
            headers=self._hdrs(),
            method=method,
        )
        return self._raw(req)

    def get(self, path: str) -> tuple[int, object]:
        return self._req("GET", path)

    def post(self, path: str, body=None) -> tuple[int, object]:
        return self._req("POST", path, body)

    def put(self, path: str, body: dict) -> tuple[int, object]:
        return self._req("PUT", path, body)

    def delete(self, path: str) -> tuple[int, object]:
        return self._req("DELETE", path)

    # ── user CRUD ──────────────────────────────────────────────────────────

    def create_user(self, username: str, **kwargs) -> tuple[int, object]:
        body = {
            "username": username,
            "proxies": {"vless": {}},
            "inbounds": {"vless": ["VLESS TCP REALITY"]},
            "status": "active",
            **kwargs,
        }
        return self.post("/api/user", body)

    def get_user(self, username: str) -> tuple[int, object]:
        return self.get(f"/api/user/{username}")

    def delete_user(self, username: str) -> tuple[int, object]:
        return self.delete(f"/api/user/{username}")

    def revoke_sub(self, username: str) -> tuple[int, object]:
        return self.post(f"/api/user/{username}/revoke_sub")

    def restart_core(self) -> tuple[int, object]:
        return self.post("/api/core/restart")

    def get_core(self) -> tuple[int, object]:
        return self.get("/api/core")

    def get_inbounds(self) -> tuple[int, object]:
        return self.get("/api/inbounds")

    def get_admin(self) -> tuple[int, object]:
        return self.get("/api/admin")

    def modify_user(self, username: str, **kwargs) -> tuple[int, object]:
        return self.put(f"/api/user/{username}", kwargs)

    def get_sub(self, sub_path: str) -> tuple[int, str]:
        """Fetch a subscription URL (no auth). Returns (status, raw_text)."""
        req = urllib.request.Request(f"{self.url}{sub_path}", method="GET")
        try:
            with urllib.request.urlopen(req, context=_SSL) as r:
                return r.status, r.read().decode()
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode()

    # ── arbitrary-token helpers ────────────────────────────────────────────

    def authed_get(self, path: str, token: str) -> tuple[int, object]:
        req = urllib.request.Request(
            f"{self.url}{path}",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            method="GET",
        )
        return self._raw(req)

    def raw_login(self, username: str, password: str) -> tuple[int, object]:
        payload = urllib.parse.urlencode(
            {"username": username, "password": password}
        ).encode()
        req = urllib.request.Request(
            f"{self.url}/api/admin/token",
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        return self._raw(req)


# ── Docker helpers ─────────────────────────────────────────────────────────


def docker_compose(
    *args: str, capture: bool = True, timeout: int = 120
) -> subprocess.CompletedProcess:
    cmd = ["docker", "compose", *args]
    return subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
        cwd=COMPOSE_DIR,
        timeout=timeout,
    )


def container_logs(tail: int = 60) -> str:
    r = docker_compose("logs", "--no-color", f"--tail={tail}", "marzban")
    return r.stdout.strip()


class LogWindow:
    """Captures new log lines emitted during the ``with`` block.

    Uses docker --since with a UTC timestamp so repeated identical log
    messages from prior runs are never confused with current-run events.
    """

    def __init__(self) -> None:
        self._since: str = ""

    def __enter__(self) -> "LogWindow":
        import datetime

        # Record the wall-clock moment we opened the window.
        # Add a small negative buffer so we don't miss lines logged in the
        # same second as __enter__.
        t = datetime.datetime.utcnow() - datetime.timedelta(seconds=1)
        self._since = t.strftime("%Y-%m-%dT%H:%M:%SZ")
        return self

    def __exit__(self, *_) -> None:
        pass

    def new_lines(self, tail: int = 200) -> list[str]:
        r = docker_compose(
            "logs", "--no-color", f"--tail={tail}", "--since", self._since, "marzban"
        )
        return r.stdout.strip().splitlines()

    def contains(self, text: str) -> bool:
        return any(text in l for l in self.new_lines())

    def print_new(self, indent: str = "     ") -> None:
        for l in self.new_lines():
            print(f"{indent}{l.strip()}")


def wait_for_marzban(timeout: int = 60, poll: float = 1.0) -> float:
    """Poll /api/core until Marzban responds. Returns seconds waited."""
    c = MarzbanClient.__new__(MarzbanClient)
    c.url = MARZBAN_URL
    c.token = ""
    c.auth_at = 0.0
    start = time.time()
    deadline = start + timeout
    while time.time() < deadline:
        try:
            c._login(ADMIN_USER, ADMIN_PASS)
            status, _ = c.get_core()
            if status == 200:
                return time.time() - start
        except Exception:
            pass
        time.sleep(poll)
    raise TimeoutError(f"Marzban did not start within {timeout}s")


def wait_next_second(pad: float = 0.02) -> None:
    """Block until the wall-clock integer-second advances.

    Marzban's subscription token is second-granular: two revoke_sub calls
    issued within the same second will produce the same sub-path token
    (only the UUID rotates).  This helper ensures the clock has actually
    ticked before the caller proceeds, making such tests deterministically
    stable.

    ``pad`` adds a small extra sleep (seconds) after the tick so that a
    slow scheduler cannot slip back into the previous second window.
    """
    t0 = int(time.time())
    while int(time.time()) == t0:
        time.sleep(0.005)  # spin in 5 ms steps — negligible CPU
    time.sleep(pad)


# ── JWT decode (no verification) ───────────────────────────────────────────


def decode_jwt(token: str) -> dict:
    parts = token.split(".")
    if len(parts) != 3:
        return {}
    pad = parts[1] + "=" * (-len(parts[1]) % 4)
    return json.loads(base64.urlsafe_b64decode(pad))


# ── SQLite helper (for quota injection) ────────────────────────────────────


def sqlite_exec(sql: str, params: tuple = ()) -> list:
    """Run SQL against the Marzban SQLite DB via docker exec python3."""
    script = (
        "import sqlite3, json; "
        f"c = sqlite3.connect('/var/lib/marzban/db.sqlite3'); "
        f"rows = c.execute({sql!r}, {params!r}).fetchall(); "
        "c.commit(); "
        "print(json.dumps(rows))"
    )
    r = docker_compose("exec", "-T", "marzban", "python3", "-c", script)
    if r.returncode != 0:
        raise RuntimeError(f"sqlite_exec failed: {r.stderr}")
    return json.loads(r.stdout.strip())


# ── Test result tracker ────────────────────────────────────────────────────


class Result:
    def __init__(self, name: str) -> None:
        self.name = name
        self.passed = 0
        self.failed = 0
        self.measurements: list[tuple[str, str]] = []

    def check(self, label: str, cond: bool, detail: str = "") -> bool:
        msg = label + (f" — {detail}" if detail else "")
        if cond:
            ok(msg)
            self.passed += 1
        else:
            fail(msg)
            self.failed += 1
        return cond

    def measure(self, label: str, value) -> None:
        self.measurements.append((label, str(value)))
        row(label, value)

    def summary(self) -> bool:
        section(f"RESULT — {self.name}")
        for k, v in self.measurements:
            row(k, v)
        total = self.passed + self.failed
        if self.failed == 0:
            ok(f"All {total} assertions passed")
        else:
            fail(f"{self.failed} / {total} assertions failed")
        passed = self.failed == 0
        # append to results log
        ts = time.strftime("%Y-%m-%dT%H:%M:%S")
        flag = "PASS" if passed else "FAIL"
        line = f"{ts}  [{flag}]  {self.name}\n"
        with open(RESULTS_DIR / "run.log", "a", encoding="utf-8") as f:
            f.write(line)
            for k, v in self.measurements:
                f.write(f"        {k}: {v}\n")
        return passed


# ── Cleanup guard ──────────────────────────────────────────────────────────


class CleanupGuard:
    """Ensures test users are deleted even if a test throws."""

    def __init__(self, client: MarzbanClient, *usernames: str) -> None:
        self._client = client
        self._usernames = list(usernames)

    def add(self, username: str) -> None:
        self._usernames.append(username)

    def __enter__(self) -> "CleanupGuard":
        return self

    def __exit__(self, *_) -> None:
        for u in self._usernames:
            try:
                self._client.delete_user(u)
            except Exception:
                pass
