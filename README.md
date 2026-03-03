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

Download `sing-box.exe` from the official releases page — make sure to grab a build that includes the `with_gvisor` tag (e.g. `sing-box-1.x.x-windows-amd64.zip`):

> **https://github.com/SagerNet/sing-box/releases**

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

---

## Server Setup (Oracle Cloud – Ubuntu + sing-box + REALITY)

### Environment

- Provider: Oracle Cloud, Ubuntu 22.04 LTS
- Port: `443` (blends with normal HTTPS traffic)
- Protocol: VLESS + REALITY
- Core: sing-box (no TLS certificate required)

### 1. Firewall

Oracle Cloud console → add ingress rule: TCP port 443, source `0.0.0.0/0`.

If UFW is enabled on the instance:

```bash
sudo ufw allow 443/tcp
```

### 2. Install sing-box

```bash
wget https://github.com/SagerNet/sing-box/releases/latest/download/sing-box-1.x.x-linux-amd64.tar.gz
tar -xvf sing-box-*.tar.gz
sudo mv sing-box-*/sing-box /usr/local/bin/
sudo chmod +x /usr/local/bin/sing-box
sing-box version
```

### 3. Generate REALITY keypair

```bash
sing-box generate reality-keypair
```

- **PublicKey** → goes in the client `.env` as `VPN_PUBLIC_KEY`
- **PrivateKey** → stays on the server in `config.json`

### 4. Server config

```bash
sudo mkdir -p /etc/sing-box
sudo nano /etc/sing-box/config.json
```

```json
{
  "log": { "level": "warn" },
  "inbounds": [
    {
      "type": "vless",
      "tag": "vless-in",
      "listen": "::",
      "listen_port": 443,
      "users": [
        {
          "uuid": "YOUR-UUID-HERE",
          "flow": "xtls-rprx-vision"
        }
      ],
      "tls": {
        "enabled": true,
        "server_name": "www.microsoft.com",
        "reality": {
          "enabled": true,
          "handshake": {
            "server": "www.microsoft.com",
            "server_port": 443
          },
          "private_key": "YOUR_PRIVATE_KEY",
          "short_id": []
        }
      }
    }
  ],
  "outbounds": [{ "type": "direct" }]
}
```

Replace `YOUR-UUID-HERE` and `YOUR_PRIVATE_KEY`. `short_id` can stay empty.

### 5. systemd service

```bash
sudo nano /etc/systemd/system/sing-box.service
```

```ini
[Unit]
Description=sing-box Service
After=network.target

[Service]
ExecStart=/usr/local/bin/sing-box run -c /etc/sing-box/config.json
Restart=on-failure
User=root

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now sing-box
sudo systemctl status sing-box
```

### 6. Verify

```bash
sudo ss -tulnp | grep 443
```

Should show sing-box listening on port 443.
