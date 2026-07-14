# RealityTunnel — Regression Tests

## Configuration Drift Check

```
tests/regression/verify_config_sync.py
```

Validates that the **live Contabo Xray runtime** matches the v1.0.0 known-good baseline.

### What It Catches

The three configuration drift bugs that caused hours of debugging after initial deployment:

| Bug | Root Cause | Check |
|-----|------------|-------|
| SNI mismatch | `www.apple.com.cn` was in `serverNames` instead of `dl.google.com` | ✓ SNI check |
| Short ID mismatch | Client sent a non-empty short ID that didn't exist in `shortIds` | ✓ Short ID check |
| Flow mismatch | Client used `xtls-rprx-vision`; Marzban provisioned with empty flow | ✓ Dest/port consistency |

### Running

```bash
# Requires SSH access to Contabo (key at ~/.ssh/id_ed25519)
python tests/regression/verify_config_sync.py
```

Exit code `0` = clean. Exit code `1` = drift detected or test failed to run.

### Updating the Baseline

If you intentionally change the server config (e.g., rotate keys, change SNI), update the `BASELINE` dict at the top of the script **before** committing:

```python
BASELINE = {
    "sni": "dl.google.com",
    "short_id": "",
    "port": 443,
    "dest": "dl.google.com:443",
    "public_key_prefix": "EO7aAL",
    "flow": "",
}
```

### Requirements

```
No Python packages required beyond stdlib — uses subprocess + ssh.
ssh must be on PATH and ~/.ssh/id_ed25519 must have access to ak@217.216.79.209.
```
