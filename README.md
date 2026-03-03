# RealityTunnel

A compact WinUI 3 VPN client for Windows that tunnels all traffic through a VLESS + REALITY server via [sing-box](https://github.com/SagerNet/sing-box).

**Features:** glassmorphism floating widget · system tray · auto-connect · connection timer · exit IP display · auto-retry with backoff · server IP saved across restarts.

---

## Requirements

- Windows 10/11 (build 19041+)
- `sing-box.exe` v1.13+ (with `with_gvisor` tag) placed next to the `.exe`
- Run as **Administrator** (required for TUN adapter + routing)

---

## Setup

### 1. Clone & configure secrets

```powershell
git clone https://github.com/adikul1023/RealityTunnel.git
cd RealityTunnel
Copy-Item .env.example .env
```

Edit `.env` and fill in your server credentials:

```env
VPN_UUID=your-vless-uuid
VPN_PUBLIC_KEY=your-reality-public-key
VPN_SNI=www.microsoft.com   # SNI used for REALITY handshake
VPN_SHORT_ID=               # leave blank if not used
```

### 2. Build

```powershell
dotnet publish RealityTunnel.sln -c Release -r win-x64 --self-contained true
```

Output: `bin\x64\Release\net8.0-windows10.0.19041.0\win-x64\publish\`

### 3. Add sing-box

Copy `sing-box.exe` into the publish folder alongside `RealityTunnel.exe`.

### 4. Run

Launch `RealityTunnel.exe` as Administrator, enter your server IP, and click **Connect**.

---

## How it works

On connect the app:
1. Reads `.env` and `config.template.json`, substitutes all `{{PLACEHOLDER}}` values
2. Launches `sing-box` with a TUN adapter (`stack: mixed`, `auto_route: false`)
3. Assigns IP `10.0.85.2/24` to the TUN adapter via `netsh`
4. Adds routes: server IP → real gateway (loop prevention), `0.0.0.0/1` + `128.0.0.0/1` → TUN gateway

On disconnect all routes are removed and sing-box is terminated.

---

## Files

| File | Purpose |
|---|---|
| `.env` | Your secrets — **gitignored, never committed** |
| `.env.example` | Template to copy → `.env` |
| `config.template.json` | sing-box config with `{{PLACEHOLDER}}` variables |
| `XrayController.cs` | Manages sing-box process + TUN routing |
| `TrayIcon.cs` | System tray (pure Win32, no WinForms) |
| `AppSettings.cs` | Persists server IP to `%LocalAppData%\RealityTunnel\` |
