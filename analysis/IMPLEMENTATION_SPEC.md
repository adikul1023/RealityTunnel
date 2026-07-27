# Implementation Specification

This document details the public interfaces, dependencies, inputs, outputs, and failure modes for every core service in the rebuilt architecture.

---

## 1. AuthenticationService (Core)

**Purpose:**
Handles user login, token acquisition, and logs the user in.

**Inputs:**
- User Credentials (Email, Password)
- Refresh Token (internal)

**Outputs:**
- Secure JWT Access Token & Refresh Token (Persisted)

**Dependencies:**
- `IApiClient`
- `ISecureStorage`
- `ISessionManager` (Updates the session with the user details and JWT on success)

**Public Interface:**
```csharp
Task<Result<AuthResponse, AuthenticationError>> LoginAsync(string email, string password);
Task<Result<bool, AuthenticationError>> LogoutAsync();
Task<Result<string, AuthenticationError>> GetValidAccessTokenAsync();
```

**Failure Modes:**
- `InvalidCredentials`: Wrong email or password.
- `NetworkTimeout`: Backend unreachable.
- `TokenExpired`: Refresh token invalid.

---

## 2. ApiClient (Core)

**Purpose:**
Centralized HTTP client wrapper. Handles JSON serialization and token injection. Contains NO hostname literals.

**Inputs:**
- API Route (e.g., `/api/client/config`)

**Outputs:**
- Strongly typed Data Transfer Objects (DTOs)

**Dependencies:**
- `HttpClientFactory`
- `IDomainResolver` (Provides the base URLs)
- `IAuthService` (To fetch the JWT bearer token for authorized endpoints)

**Public Interface:**
```csharp
Task<Result<TResponse, ApiError>> GetAsync<TResponse>(string endpoint);
Task<Result<TResponse, ApiError>> PostAsync<TRequest, TResponse>(string endpoint, TRequest payload);
```

**Failure Modes:**
- `NetworkTimeout`: Connection dropped.
- `Unauthorized`: 401 response.
- `SerializationError`: JSON mapping failed.

---

## 3. ConnectionProvisioningService (Core)

**Purpose:**
The supreme orchestrator for connecting to the VPN. Ties together authentication, configuration building, and the VPN execution layer.

**Inputs:**
- None (Triggered by the UI 'Connect' button)

**Outputs:**
- State transitions (Connecting -> Connected)

**Dependencies:**
- `IApiClient` (to download the `ServerProfileDto`)
- `IConfigurationBuilder` (to transform DTO to `VPNConfig`)
- `IVpnService` (to execute the resulting config)
- `ISessionManager` (to ensure JWT is valid and user is logged in)

**Public Interface:**
```csharp
Task<Result<bool, VpnError>> ConnectAsync();
Task<Result<bool, VpnError>> DisconnectAsync();
```

**Failure Modes:**
- `NotAuthenticated`: User has no valid session.
- `ProvisioningFailed`: Backend rejected the config request.
- `ConfigGenerationFailed`: Configuration builder failed.
- `VpnExecutionFailed`: Helper failed to start the VPN.

---

## 4. ConfigurationBuilder (Configuration)

**Purpose:**
Pure logic class that translates backend DTOs into the `VPNConfig` object graph and raw JSON required by the VPN core.

**Inputs:**
- `ServerProfileDto`

**Outputs:**
- `VPNConfig` (containing the sing-box JSON string and metadata)

**Dependencies:**
- None (Pure logic, fully unit-testable).

**Public Interface:**
```csharp
Result<VPNConfig, ConfigurationError> BuildSingboxConfig(ServerProfileDto profile);
```

**Failure Modes:**
- `MissingRequiredField`: Backend DTO is missing crucial data.
- `TemplateError`: Failed to serialize or merge the base routing template.

---

## 5. WindowsVpnService (Core)

**Purpose:**
Acts exclusively as the IPC bridge to the elevated Helper service. It knows nothing about APIs, DTOs, or JWTs.

**Inputs:**
- `VPNConfig` object (from the Provisioner)

**Outputs:**
- `StartVpnResponse` (Success/Failure status from the Helper)
- Event streams (Logs, Connection Stats)

**Dependencies:**
- Named Pipe Client stream (to talk to Helper)
- `IFeatureManager` (to toggle Experimental protocols or Kill Switch in the IPC request)

**Public Interface:**
```csharp
event EventHandler<ApplicationState> StateChanged;
event EventHandler<VpnStats> StatsUpdated;

Task<Result<bool, VpnError>> ConnectAsync(VPNConfig config);
Task<Result<bool, VpnError>> DisconnectAsync();
```

**Failure Modes:**
- `HelperNotRunning`: The Windows service is stopped.
- `IpcTimeout`: Named pipe connection failed.
- `HelperError`: The Helper returned a failure response.

---

## 6. HelperService (Helper)

**Purpose:**
Runs as `SYSTEM`/Administrator. Receives a strictly typed `StartVpnRequest`, manages the Wintun adapter, starts `sing-box.exe`, and implements the kill switch.

**Inputs:**
- `StartVpnRequest` (IPC payload containing JSON Config, KillSwitch boolean, Timestamp, etc.)
- Disconnect command

**Outputs:**
- `StartVpnResponse` (Success flag, Error message, PID, InterfaceName)
- Standard Output/Error streams of `sing-box` forwarded back

**Dependencies:**
- `sing-box.exe`
- `wintun.dll`

**Failure Modes:**
- `DriverError`: Failed to install or bind Wintun adapter.
- `ProcessCrash`: Sing-box exited with a non-zero code.
- `RoutingError`: Failed to modify Windows routing tables.

---

## 7. Infrastructure Services (Infrastructure)

### A. DomainResolver (`IDomainResolver`)
Provides canonical base URLs for the app (e.g., `ApiBaseUrl`, `EdgeHost`, `DownloadBase`), allowing easy switching between production, staging, and future failovers.

### B. SessionManager (`ISessionManager`)
Holds the active `CurrentSession` state (User profile, Subscription level, JWT, ConnectedSince, BytesUploaded). The single source of truth for the UI bindings.

### C. FeatureManager (`IFeatureManager`)
Provides boolean flags for gradual rollouts (e.g., `EnableKillSwitch`, `EnableHeartbeat`, `EnableTelemetry`, `EnableUpdater`).

### D. SecureStorageService (`ISecureStorage`)
Uses Windows DPAPI to safely encrypt and decrypt the JWT and Refresh tokens on disk.
