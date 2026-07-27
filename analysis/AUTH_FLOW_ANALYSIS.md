# Authentication Flow Analysis

## Old Authentication (Legacy V1)
In the older versions of the app, authentication was completely tied to the VPN protocol and lacked a central identity system.
- **UUID / VLESS**: Users authenticated to the VPN servers by directly inputting a UUID. This UUID was essentially the user's only credential.
- **Profile loading**: The client either stored a raw JSON profile containing the VLESS configuration or downloaded a static JSON file.
- **Connection Sequence**: 
  1. User clicks Connect.
  2. The raw profile string (with the UUID embedded) is written to a temporary JSON file.
  3. The Helper service starts `sing-box.exe` passing the path to this JSON file.
- **Credentials Storage**: UUIDs were stored in plain text configuration files (e.g., `config.template.json`) or insecure settings files.
- **How Helper starts VPN**: The main application communicates with the Helper service via named pipes. The Helper service, running as `SYSTEM`/Administrator, executes the sing-box binary as a child process and configures the `wintun` virtual network adapter.

## Modern Replacement

The modernized flow entirely decouples user identity from VPN credentials. It relies on a central Billing/Auth API.

1. **Login**
   - User inputs Email/Password (or uses OAuth/TOTP) in the UI.
   - The UI calls the central Auth API (`POST /api/auth/login`).
   - The API returns a secure `JWT Access Token` and a `Refresh Token`.

2. **JWT**
   - The Client securely stores the JWT using Windows DPAPI (`SecureStorageService`).
   - All subsequent API requests are authenticated via the `Authorization: Bearer <token>` header.

3. **Device Registration**
   - After login, the client submits a hardware fingerprint (`POST /api/devices`).
   - The API registers the device, ensuring the user has not exceeded their active device limit.
   - A unique `device_id` is assigned and associated with the JWT session.

4. **Signed Profile Download**
   - The client requests VPN configurations (`GET /api/client/config`).
   - The backend dynamic generates a specific sing-box configuration (JSON).
   - The backend injects temporary, short-lived VLESS UUIDs/Shadowsocks passwords that are specific to that device and session.
   - The configuration is securely downloaded over HTTPS.

5. **VPN Execution**
   - The UI sends the secure config payload to the Helper Service via IPC.
   - The Helper validates the payload structure, writes it to a protected temporary directory, and starts sing-box.
   - Connections to `edge.stealthy.co.in` proceed using the dynamically provisioned credentials.
