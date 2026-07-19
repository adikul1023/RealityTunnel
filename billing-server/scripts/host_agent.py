import os
import time
import json
import hmac
import hashlib
import secrets
import subprocess
import logging
import threading
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("host_agent")

COMMAND_FILE = os.getenv("OVERREALITY_IPC_FILE", "/opt/realitytunnel/ipc/commands.txt")
IPC_SECRET = os.getenv("IPC_SECRET_KEY", "DEV_IPC_SECRET")
MAX_AGE_SECONDS = 60

# ── Nonce store ────────────────────────────────────────────────────────────────
# Maps nonce -> expiry_time. Protects against replay within the allowed window.
_nonce_lock = threading.Lock()
_seen_nonces: dict[str, float] = {}


def _evict_expired_nonces() -> None:
    """Remove nonces that are past the replay window."""
    now = time.time()
    expired = [n for n, exp in _seen_nonces.items() if now > exp]
    for n in expired:
        del _seen_nonces[n]


def _check_and_record_nonce(nonce: str, timestamp: int) -> bool:
    """
    Returns True if the nonce is fresh (not seen before).
    Records the nonce with an expiry of timestamp + MAX_AGE_SECONDS.
    Returns False if the nonce was already used.
    """
    with _nonce_lock:
        _evict_expired_nonces()
        if nonce in _seen_nonces:
            return False
        _seen_nonces[nonce] = timestamp + MAX_AGE_SECONDS
        return True


# ── HMAC verification ──────────────────────────────────────────────────────────

def _compute_hmac(service: str, action: str, timestamp: int, nonce: str, secret: str) -> str:
    """Compute the expected HMAC for a command payload."""
    msg = f"{service}:{action}:{timestamp}:{nonce}"
    return hmac.new(
        secret.encode("utf-8"),
        msg.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


def verify_and_validate(payload: dict) -> tuple[bool, str]:
    """
    Validate an IPC command payload. Returns (valid: bool, reason: str).
    Checks:
      1. Required fields present
      2. HMAC matches
      3. Timestamp within MAX_AGE_SECONDS
      4. Nonce not previously seen (replay prevention)
    """
    required = {"service", "action", "timestamp", "nonce", "hmac"}
    missing = required - payload.keys()
    if missing:
        return False, f"Missing fields: {missing}"

    service = payload["service"]
    action = payload["action"]
    timestamp = payload["timestamp"]
    nonce = payload["nonce"]
    received_hmac = payload["hmac"]

    # 1. HMAC verification
    expected_hmac = _compute_hmac(service, action, timestamp, nonce, IPC_SECRET)
    if not hmac.compare_digest(expected_hmac, received_hmac):
        return False, "HMAC verification failed"

    # 2. Timestamp window
    now = int(time.time())
    if abs(now - timestamp) > MAX_AGE_SECONDS:
        return False, f"Timestamp too old or skewed (delta={abs(now - timestamp)}s)"

    # 3. Nonce freshness (replay check)
    if not _check_and_record_nonce(nonce, timestamp):
        return False, f"Nonce '{nonce}' already used (replay attack prevented)"

    return True, "ok"


# ── Command dispatch ───────────────────────────────────────────────────────────

ALLOWED_SERVICES = {"marzban", "xray", "caddy", "redis", "scheduler"}


def dispatch_command(service: str, action: str) -> None:
    """Execute the validated infrastructure command."""
    if service not in ALLOWED_SERVICES:
        logger.error("Unknown service '%s' — refusing to dispatch", service)
        return

    if action == "restart":
        logger.info("Restarting service: %s", service)
        try:
            subprocess.run(
                ["docker", "restart", f"billing-server-{service}-1"],
                check=True,
                timeout=30,
            )
            logger.info("Service %s restarted successfully.", service)
        except subprocess.CalledProcessError as e:
            logger.error("Failed to restart %s: %s", service, e)
        except subprocess.TimeoutExpired:
            logger.error("Restart of %s timed out.", service)

    elif action == "reload" and service == "xray":
        logger.info("Reloading xray configuration...")
        try:
            subprocess.run(
                ["docker", "kill", "--signal=SIGHUP", "billing-server-xray-1"],
                check=True,
                timeout=10,
            )
            logger.info("Xray reloaded successfully.")
        except subprocess.CalledProcessError as e:
            logger.error("Failed to reload xray: %s", e)

    else:
        logger.warning("Unknown action '%s' for service '%s'", action, service)


# ── Main polling loop ──────────────────────────────────────────────────────────

def process_commands() -> None:
    if not os.path.exists(COMMAND_FILE):
        return

    try:
        with open(COMMAND_FILE, "r") as f:
            lines = f.readlines()

        # Clear immediately after reading to prevent double-processing
        with open(COMMAND_FILE, "w") as f:
            f.write("")

        for line in lines:
            line = line.strip()
            if not line:
                continue

            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                logger.error("Failed to decode command JSON: %.120s", line)
                continue

            valid, reason = verify_and_validate(payload)
            if not valid:
                logger.error(
                    "Rejected IPC command [%s]: %.120s",
                    reason, line
                )
                continue

            service = payload["service"]
            action = payload["action"]
            logger.info(
                "Authenticated command: service=%s action=%s nonce=%s",
                service, action, payload["nonce"]
            )
            dispatch_command(service, action)

    except Exception as e:
        logger.error("Error processing commands: %s", e)


def main() -> None:
    logger.info("Starting authenticated host agent, polling %s", COMMAND_FILE)
    os.makedirs(os.path.dirname(COMMAND_FILE), exist_ok=True)
    if not os.path.exists(COMMAND_FILE):
        with open(COMMAND_FILE, "w") as f:
            f.write("")

    while True:
        process_commands()
        time.sleep(1)


if __name__ == "__main__":
    main()
