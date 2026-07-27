# Domain Audit

## `api.stealthy.co.in`
- **File**: `PROJECT_STATE.md`, Line 10
- **Current Value**: `api.stealthy.co.in`
- **Purpose**: Documentation of the Oracle Cloud Billing API endpoint.
- **Replacement required?**: NO

- **File**: `Services/OracleApiClient.cs`
- **Current Value**: Dynamic based on config or hardcoded fallback.
- **Purpose**: Base URL for all Authentication and Config API requests (`/api/client/config`, `/api/devices/auth`, etc.)
- **Replacement required?**: YES (Should be centralized into an `appsettings.json` or Shared configuration).

## `edge.stealthy.co.in`
- **File**: `PROJECT_STATE.md`, Line 18
- **Current Value**: `edge.stealthy.co.in`
- **Purpose**: Documentation of the Marzban Edge Server.
- **Replacement required?**: NO

- **File**: JSON Profiles returned by API
- **Current Value**: `edge.stealthy.co.in`
- **Purpose**: SNI and server address in sing-box configurations.
- **Replacement required?**: YES (Must be dynamically served by backend, not hardcoded on client).

## `RealityTunnel` / `OverREALITY`
- **File**: `MainWindow.xaml`
- **Current Value**: `OverREALITY`
- **Purpose**: UI Title and Branding.
- **Replacement required?**: NO (Unless rebranding occurs).

- **File**: `Services/SecureStorageService.cs`
- **Current Value**: `RealityTunnel.Vault`
- **Purpose**: Container name for DPAPI token storage.
- **Replacement required?**: NO

- **File**: `.csproj` files, namespaces
- **Current Value**: `RealityTunnel.*`
- **Purpose**: .NET Namespaces and project assemblies.
- **Replacement required?**: YES (Will be refactored into the new Solution structure).
