# UI
- Login screen (MainWindow.xaml)
- Dashboard stats and user details (MainWindow.xaml)
- Settings toggle (MainWindow.xaml)
- Tray icon integration (TrayIcon.cs)
- Notifications (App.xaml.cs)
- Glass effects and modern styling elements (WinUI 3 basic windowing)

# VPN
- Start VPN (VpnSessionManager.cs)
- Stop VPN (VpnSessionManager.cs)
- Sing-box wrapper execution (VpnBackendResolver.cs)
- Helper service communication (RealityTunnel.Helper)
- Reconnect logic (DeviceHeartbeatService.cs)

# Backend
- JWT Login and Authentication (AuthenticationService.cs)
- Profile/Config download (OracleApiClient.cs, ConfigurationProvider.cs)
- Health check and Device Heartbeat (DeviceHeartbeatService.cs)
- Secure Storage for tokens (SecureStorageService.cs)

# Utilities
- Logging (StartupLogger.cs, ClientLogger.cs)
- IPC Named Pipes (between App and Helper)
- Service registration and startup (setup.csproj / build_setup.ps1)
