# Migration Plan

## Phase 1: Project Skeleton & Shared Contracts
- **Goal:** Create the `.sln` and base projects. Define all Interfaces (`IAuthService`, `IVpnService`, `IApiClient`, `IDomainResolver`, `IFeatureManager`, `ISessionManager`, etc.), `ApplicationState`, and Error Models in `Shared`.
- **Dependencies:** None.
- **Complexity:** Low.
- **Risk:** Low.

## Phase 2: Infrastructure
- **Goal:** Implement the foundational cross-cutting concerns in `OverREALITY.Infrastructure`. This includes `HttpClient` wrappers, Logging, `SecureStorageService`, `Settings`, Dependency Injection setup, `DomainResolver`, `FeatureManager`, and `SessionManager`.
- **Dependencies:** Phase 1.
- **Complexity:** Medium.
- **Risk:** Low.

## Phase 3: Authentication & API
- **Goal:** Implement `ApiClient` and `AuthenticationService` in `Core`. Handle JWT tokens, login, and device registration API calls securely tied to the `SessionManager`.
- **Dependencies:** Phase 2.
- **Complexity:** Medium.
- **Risk:** Medium.

## Phase 4: Configuration Builder
- **Goal:** Implement `ConfigurationBuilder` in `Configuration` project. Take Backend DTOs and convert them into validated sing-box JSON configuration strings.
- **Dependencies:** Phase 1.
- **Complexity:** Medium.
- **Risk:** Low (Easily unit testable without network).

## Phase 5: Connection Provisioning
- **Goal:** Implement `ConnectionProvisioningService` in `Core`. This orchestrates the connection flow: validates JWT -> downloads DTO -> builds config via `ConfigurationBuilder` -> outputs `VPNConfig`.
- **Dependencies:** Phase 3, Phase 4.
- **Complexity:** Medium.
- **Risk:** Medium.

## Phase 6: Helper Service Foundation
- **Goal:** Build the elevated Windows Service (`OverREALITY.Helper`). Establish Named Pipes communication where the Helper listens for a strictly typed `StartVpnRequest` IPC contract.
- **Dependencies:** Phase 1.
- **Complexity:** High.
- **Risk:** High (Requires IPC security, UAC handling).

## Phase 7: VPN Service (Core to Helper IPC)
- **Goal:** Implement `WindowsVpnService : IVpnService` in Core. It accepts the `VPNConfig` from the Provisioning Service, packages it into a `StartVpnRequest`, and sends it to the Helper.
- **Dependencies:** Phase 5, Phase 6.
- **Complexity:** Medium.
- **Risk:** Medium.

## Phase 8: Sing-box & Networking (Helper Internal)
- **Goal:** Implement the logic in `Helper` to wrap sing-box execution, apply the received `StartVpnRequest` parameters (DNS, Kill Switch), and manage Wintun adapter state.
- **Dependencies:** Phase 6.
- **Complexity:** High.
- **Risk:** High.

## Phase 9: UI Foundation & MVVM
- **Goal:** Setup WinUI 3 `App.xaml`, initial `MainWindow`, `NavigationView`, and DI container linking interfaces to implementations. Create base ViewModels bound to `ApplicationState` and `ISessionManager`.
- **Dependencies:** Phase 1 to Phase 8.
- **Complexity:** Medium.
- **Risk:** Low.

## Phase 10: UI Integration (Login & Dashboard)
- **Goal:** Connect `LoginViewModel` to `AuthenticationService`. Connect `DashboardViewModel` to `ConnectionProvisioningService`. React to `ApplicationState` changes cleanly.
- **Dependencies:** Phase 9.
- **Complexity:** Medium.
- **Risk:** Low.

## Phase 11: Settings, Notifications & Heartbeat
- **Goal:** Implement `DeviceHeartbeatService`. Build the Settings View. Implement System Tray minimization, background process lifecycle, and toast notifications.
- **Dependencies:** Phase 10.
- **Complexity:** Medium.
- **Risk:** Low.

## Phase 12: Installer & Deployment
- **Goal:** Create a modern installer that drops the files, registers the `Helper` service securely, and launches the UI.
- **Dependencies:** Phase 11.
- **Complexity:** Medium.
- **Risk:** High.
