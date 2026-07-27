# UI Rebuild Plan

## Review of the Current Working UI (`MainWindow.xaml`)

### Good Parts
- **Tray Icon Support**: Background operations and minimize-to-tray keep the VPN active without cluttering the taskbar.
- **Visual Feedback**: Simple toggles and states (Connected/Disconnected/Connecting).
- **Core Features Present**: Settings toggle, connection button, data transfer readouts.

### Bad Parts
- **Monolithic Code-Behind**: `MainWindow.xaml.cs` handles UI logic, API calls, error handling, and IPC communication. This makes it impossible to unit test and very hard to maintain.
- **Hardcoded Layouts**: Margins, paddings, and control sizes are hardcoded, meaning the UI does not scale well on different DPI settings or window sizes.
- **Tight Coupling**: UI depends directly on `AuthenticationService` and `OracleApiClient` concrete implementations rather than interfaces.

### Outdated Elements
- Custom navigation implemented by hiding/showing Grids or StackPanels instead of using standard `Frame` or `NavigationView`.
- Inconsistent spacing and margins compared to standard Windows 11 design language.
- Inline colors and brushes instead of using centralized resource dictionaries.

## Suggested Modern Redesign (WinUI 3)

### 1. Architecture: MVVM (Model-View-ViewModel)
- Implement `CommunityToolkit.Mvvm` for ViewModels (`ObservableObject`, `RelayCommand`).
- Remove all business logic from `.xaml.cs` code-behind files.
- Inject services into ViewModels via Dependency Injection (`Microsoft.Extensions.DependencyInjection`).

### 2. Layout & Navigation
- **NavigationView**: Use the standard `Microsoft.UI.Xaml.Controls.NavigationView` for the main sidebar (Dashboard, Settings, Account).
- **Frame Navigation**: Use a central `Frame` to navigate between pages (`DashboardPage.xaml`, `SettingsPage.xaml`), rather than toggling visibility of panels.

### 3. Styling & Theming
- Move all colors, brushes, and typography to an `AppStyles.xaml` ResourceDictionary.
- Use built-in WinUI 3 Theme Resources (`SystemControlForegroundBaseHighBrush`, etc.) so the app automatically supports Light/Dark mode and Windows high-contrast themes.
- Utilize WinUI 3 Mica or Acrylic backdrop materials for the main window to give it a modern, premium feel.

### 4. Responsiveness
- Replace hardcoded `Width`/`Height` with `Grid` star sizing and responsive `StackPanel` layouts.
- Ensure the connection button and status indicators are prominent and scale correctly across DPIs.
