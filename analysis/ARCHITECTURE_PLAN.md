# Architecture Plan

The new solution (`OverREALITY.sln`) will be structured into distinct, decoupled projects to ensure maintainability, testability, and clear separation of concerns.

## Project Structure and Responsibilities

### 1. `OverREALITY.Shared`
- **Type:** Class Library (net8.0)
- **Responsibility:** Shared contracts across all projects.
- **Contents:** Interface definitions (`IAuthService`, `IVpnService`, `IApiClient`, `ISecureStorage`, `IConfigurationBuilder`, `ISettings`, `IDomainResolver`, `IFeatureManager`, `ISessionManager`), ApplicationState enums, Error Models (e.g., `VpnError`, `AuthenticationError`), DTOs, IPC Contracts (`StartVpnRequest`, `StartVpnResponse`), Constants.
- **Dependencies:** None

### 2. `OverREALITY.Infrastructure`
- **Type:** Class Library (net8.0-windows)
- **Responsibility:** Cross-cutting concerns and platform-specific implementations.
- **Contents:** `DomainResolver`, `SecureStorageService`, `SessionManager`, `FeatureManager`, `HttpClient` wrappers, `Settings`, Logging.
- **Dependencies:** `OverREALITY.Shared`

### 3. `OverREALITY.Core`
- **Type:** Class Library (net8.0)
- **Responsibility:** The central business logic engine (Platform-independent).
- **Contents:** `ConnectionProvisioningService` (Orchestrates JWT -> DTO -> Config -> VPNConfig), `AuthenticationService`, `ApiClient`, `WindowsVpnService` (IPC client only), `DeviceHeartbeatService`.
- **Dependencies:** `OverREALITY.Shared`, `OverREALITY.Configuration`

### 4. `OverREALITY.Configuration`
- **Type:** Class Library (net8.0)
- **Responsibility:** Reality/sing-box config generation.
- **Contents:** `ConfigurationBuilder`, Validation logic, JSON Serialization, Templates. Does NOT handle networking or UI. Converts backend DTOs into raw sing-box JSON configs.
- **Dependencies:** `OverREALITY.Shared`

### 5. `OverREALITY.Helper`
- **Type:** Windows Worker Service / Console App (net8.0-windows)
- **Responsibility:** The elevated background service (`requireAdministrator`).
- **Contents:** IPC Named Pipe server (accepting `StartVpnRequest`), Wintun adapter management, routing table manipulation, Sing-box process execution.
- **Dependencies:** `OverREALITY.Shared`

### 6. `OverREALITY.UI`
- **Type:** WinUI 3 App (net8.0-windows)
- **Responsibility:** The frontend presentation layer.
- **Contents:** ViewModels, Views, Converters, ResourceDictionaries. Binds strictly to `ApplicationState` and Interfaces via DI.
- **Dependencies:** `OverREALITY.Core`, `OverREALITY.Infrastructure`, `OverREALITY.Shared`, `OverREALITY.Configuration`

### 7. `OverREALITY.Installer`
- **Type:** Setup Project (WiX Toolset / InnoSetup)
- **Responsibility:** Packages the compiled output into a distributable `setup.exe` or `.msi`.
- **Contents:** Installation scripts, Windows Service registration directives.
- **Dependencies:** Output of `OverREALITY.UI` and `OverREALITY.Helper`

### 8. `OverREALITY.Tests`
- **Type:** Test Project (xUnit / NUnit)
- **Responsibility:** Quality assurance.
- **Contents:** Unit tests for Core logic, Configuration builder, and integration tests.
- **Dependencies:** `OverREALITY.Core`, `OverREALITY.Shared`, `OverREALITY.Configuration`, `OverREALITY.Infrastructure`

### 9. `Legacy` & `Docs`
- **Type:** Folders
- **Responsibility:** Archive of prior implementations and project documentation.
