# Stealthy VPN

A modern, lightweight Windows VPN client built on [sing-box](https://github.com/SagerNet/sing-box) with a native WPF UI. Designed for stealth and privacy.

---

## Features

- **Account-key based auth** — No username/password. Your account key is all you need.
- **Automatic device registration** — Registers your device on first login; recovers gracefully if your device slot is removed.
- **Seamless session restore** — Tokens are stored encrypted via Windows DPAPI and restored automatically on next launch.
- **System tray integration** — Minimize to tray, connect/disconnect without opening the main window.
- **Helper service architecture** — A privileged helper process manages the sing-box tunnel, keeping the UI unprivileged.

---

## Architecture

```
OverREALITY.UI          → WPF frontend (unprivileged)
OverREALITY.Core        → Business logic (auth, connection, token management)
OverREALITY.Infrastructure → Platform services (secure storage, HTTP, helper IPC)
OverREALITY.Helper      → Elevated helper process (manages sing-box TUN adapter)
OverREALITY.Shared      → Shared interfaces, models, errors
Stealthy.Installer      → Self-contained WPF installer (no dependencies required)
```

---

## Requirements

- Windows 10 / 11 (x64)
- .NET 8 Runtime (Desktop)
- Administrator rights for the Helper process (UAC prompt on first launch)

---

## Building from Source

```powershell
# Restore and build all projects
dotnet build OverREALITY.sln -c Release

# Publish the UI (framework-dependent, win-x64)
dotnet publish src/OverREALITY.UI/OverREALITY.UI.csproj -c Release -r win-x64 --self-contained false

# Publish the Helper (must be built separately)
dotnet publish src/OverREALITY.Helper/OverREALITY.Helper.csproj -c Release -r win-x64 --self-contained false
```

Copy `sing-box.exe`, `wintun.dll`, and `environment.json` (provided separately) into the publish output directory.

---

## Configuration

Server configuration is fetched dynamically at runtime from the backend. The client reads `environment.json` from its working directory to determine the API base URL and provisioning endpoint.

**`environment.json` is not committed to this repository.** It contains server addresses and must be placed alongside the executable before running.

---

## Security Notes

- Tokens (access & refresh) are stored encrypted on disk using **Windows DPAPI** (per-user scope) — they cannot be read by other users or processes.
- The `master_token` (your account key) is **never stored** — it is used once at login and discarded.
- No secrets, API keys, server IPs, or credentials are present in this source code.
- The sing-box runtime config (containing VLESS UUIDs and server details) is generated at runtime and never written to a persistent location.

---

## Installation

Download `setup.exe` from the [Releases](https://github.com/adikul1023/StealthyDownloads/releases) page.

The installer:
1. Extracts all files to `C:\Program Files\Stealthy VPN`
2. Creates Desktop and Start Menu shortcuts
3. Optionally launches the app immediately

---

## License

Private / proprietary. All rights reserved.
