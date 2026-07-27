# File Map

## `MainWindow.xaml` / `MainWindow.xaml.cs`
**Purpose:** Dashboard UI and Login logic handling.
**Migration:** YES
**Reason:** Good base layout for the UI, but requires refactoring to MVVM and splitting logic.

## `RealityTunnel.Helper` (Project)
**Purpose:** Windows elevated service for managing Wintun and routing.
**Migration:** YES
**Reason:** Working implementation of privileged operations like driver interaction and network interface management.

## `Services/AuthenticationService.cs`
**Purpose:** Handles login and token acquisition.
**Migration:** YES
**Reason:** Core JWT flow is required, though requires separation from UI code.

## `Services/OracleApiClient.cs`
**Purpose:** Backend API integration for auth, heartbeat, config fetching.
**Migration:** YES
**Reason:** Modern API communication logic is solid, just needs refactoring into cleaner repositories.

## `Services/DeviceHeartbeatService.cs`
**Purpose:** Maintains device connection state with the backend.
**Migration:** YES
**Reason:** Necessary for real-time connection stats and device tracking.

## `Services/SecureStorageService.cs`
**Purpose:** Stores tokens and sensitive data via DPAPI.
**Migration:** YES
**Reason:** Cryptographically sound method for credential storage.

## `Services/VpnSessionManager.cs` / `VpnBackendResolver.cs`
**Purpose:** Starts/Stops the sing-box instance and manages the lifecycle.
**Migration:** YES
**Reason:** Necessary wrapper for sing-box execution.

## `StartupLogger.cs` / `ClientLogger.cs`
**Purpose:** Logging utilities.
**Migration:** YES
**Reason:** Robust logging needed for debugging.

## `TrayIcon.cs`
**Purpose:** Manages system tray presence.
**Migration:** YES
**Reason:** Good implementation for minimizing to tray.

## `build.ps1` / `build_setup.ps1`
**Purpose:** Scripts to package the UI, Helper, and Installer.
**Migration:** NO
**Reason:** Will need to be rewritten for the new solution structure.

## `setup/setup.csproj`
**Purpose:** C# based setup installer generator.
**Migration:** NO
**Reason:** A standard WiX toolset or modern installer (InnoSetup) should replace custom C# install logic.
