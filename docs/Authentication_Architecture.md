# Stealthy Client Authentication Architecture

This document describes the foundational authentication and session architecture for Stealthy (formerly RealityTunnel) clients (Windows & Android).

## 1. Domain Models
Shared across both platforms, standardizing how we represent identity and sessions:
- `AccountInfo`: `AccountId`, `TwoFactorEnabled`
- `DeviceRegistration`: `DeviceGuid`, `DeviceName`, `Platform`, `AppVersion`, `OsVersion`
- `JwtTokens`: `AccessToken`, `RefreshToken`, `ExpiresAt`
- `LicenseBlob`: `Payload`, `Signature` (for signed VPN profiles)
- `SessionState`: `Success`, `Expired`, `ReplayDetected`, `Offline`
- `SubscriptionInfo`: `Status`, `ExpiresAt`
- `ApiError`: Standardized error responses

## 2. Abstraction Layers

### Data Layer
- **SecureStorageService / SecureStorage**: Handles sensitive credential storage securely.
  - Windows: DPAPI via `System.Security.Cryptography.ProtectedData` (`CurrentUser` scope).
  - Android: `EncryptedSharedPreferences` (AES256_SIV / AES256_GCM).
  - In both platforms, Master Tokens are read into a `char[]` and actively zeroed out from memory after use.
- **OracleApiClient**: Handles API requests to the Oracle Control Plane (`POST /api/auth/token`, `GET /api/provisioning/profile`). 

### Business Logic (Auth Package)
- **TokenService / TokenRepository**: Manages the JWT lifecycle and state machine mapping (`SessionState`). Handled offline states, expiration checks, and token eviction when replay attacks are detected.
- **LicenseService / LicenseRepository**: Manages the signed License Blob that contains VPN routing parameters. Includes offline Ed25519 signature validation and 72-hour grace period verification logic.
- **AuthenticationService / AuthenticationManager**: Facade for the UI to login, logout, and check authentication status. Orchestrates saving the Master Token, calling Oracle API, fetching JWTs, and obtaining the License Blob.

### VPN Engine (Session Package)
- **ConfigurationProvider**: A facade that abstracts where the VPN connection parameters come from. For Phase 8.2, this relies on a fallback (manual text input) to avoid breaking the existing proven VPN engine logic.
- **VpnSessionManager / SessionManager**: The core lifecycle orchestrator for the VPN connection. Completely decoupled from Authentication. Handles connecting to Xray/Marzban, retrying on failure, and maintaining connection timers.

## 3. Dependency Injection
The architecture enforces strict decoupling between UI, Auth, and VPN Engine.
- **Windows**: Uses Microsoft's official `Microsoft.Extensions.DependencyInjection` built in `App.xaml.cs`.
- **Android**: Uses manual Dependency Injection via lazily initialized Singletons in `MainActivity.kt`.

## 4. App Links (Zero-Config Android)
The Android manifest has been prepared to handle `stealthy.com` deep links via `<intent-filter>` for `android.intent.action.VIEW`. AutoVerify is explicitly disabled until the `assetlinks.json` is published on the Stealthy domain in Phase 8.3.
