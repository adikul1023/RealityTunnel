using Microsoft.Extensions.DependencyInjection;
using Microsoft.UI;
using Microsoft.UI.Windowing;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Input;
using Microsoft.UI.Xaml.Media;
using System;
using System.Net.Http;
using System.Runtime.InteropServices;
using System.Threading.Tasks;
using Windows.Graphics;
using Windows.UI;
using RealityTunnel.Models;
using RealityTunnel.Services;

namespace RealityTunnel;

public enum NavigationState { Splash, Login, Main, Settings, FirstTimeMasterToken }

public sealed partial class MainWindow : Window
{
    // Win32 for window drag
    [DllImport("user32.dll")] private static extern bool ReleaseCapture();
    [DllImport("user32.dll")] private static extern IntPtr PostMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);
    private const uint WM_NCLBUTTONDOWN = 0x00A1;
    private const int  HTCAPTION = 2;

    private readonly AppSettings _settings = AppSettings.Load();
    private readonly TrayIcon _tray;
    private readonly DispatcherTimer _timer = new();
    private readonly HttpClient _http = new() { Timeout = TimeSpan.FromSeconds(8) };
    private readonly System.Threading.SemaphoreSlim _activationLock = new(1, 1);
    
    private readonly VpnSessionManager _sessionManager;
    private readonly AuthenticationService _authService;
    private readonly ConfigurationProvider _configProvider;
    private readonly TokenService _tokenService;
    private readonly LicenseService _licenseService;
    private readonly ClientLogger _logger;
    private readonly OracleApiClient _oracleClient;
    private readonly DeviceHeartbeatService _heartbeatService;

    private DateTime _connectedAt;

    private static readonly Color Green  = Color.FromArgb(255, 50,  205, 100);
    private static readonly Color Gray   = Color.FromArgb(255, 120, 120, 120);
    private static readonly Color Orange = Color.FromArgb(255, 255, 165,   0);

    public MainWindow(
        VpnSessionManager sessionManager, 
        AuthenticationService authService, 
        ConfigurationProvider configProvider,
        TokenService tokenService,
        LicenseService licenseService,
        ClientLogger logger,
        OracleApiClient oracleClient,
        DeviceHeartbeatService heartbeatService)
    {
        StartupLogger.Log("[8] MainWindow constructor entered");
        StartupLogger.Log("[9] Before InitializeComponent()");
        InitializeComponent();
        StartupLogger.Log("[10] After InitializeComponent()");
        _sessionManager = sessionManager;
        _authService = authService;
        _configProvider = configProvider;
        _tokenService = tokenService;
        _licenseService = licenseService;
        _logger = logger;
        _oracleClient = oracleClient;
        _heartbeatService = heartbeatService;
        _tray = new TrayIcon(this);

        var appWin = AppWindow;
        appWin.Resize(new SizeInt32(_settings.WindowWidth, _settings.WindowHeight));
        ExtendsContentIntoTitleBar = true;

        string? exeDir = System.IO.Path.GetDirectoryName(Environment.ProcessPath);
        string iconPath = System.IO.Path.Combine(exeDir ?? AppContext.BaseDirectory, "app.ico");
        if (System.IO.File.Exists(iconPath))
            AppWindow.SetIcon(iconPath);

        _timer.Tick += Timer_Tick;

        _sessionManager.OnStateChanged += SessionManager_OnStateChanged;
        _sessionManager.OnConnectedChanged += SessionManager_OnConnectedChanged;
        _sessionManager.OnRetryUpdate += SessionManager_OnRetryUpdate;
        _sessionManager.OnError += SessionManager_OnError;

        this.Closed += OnClosed;
        this.SizeChanged += MainWindow_SizeChanged;

        ApplyTheme();

        RunStartupSequence();
    }

    private static readonly Version MinimumSupportedVersion = new(1, 0, 0);

    private async void RunStartupSequence()
    {
        _logger.Log(LogLevel.INFO, "STARTUP", "Starting client initialization sequence");
        SetNavigationState(NavigationState.Splash);

        var profile = _configProvider.GetCachedProfile();

        var tokens = _tokenService.CurrentTokens;
        _logger.Log(LogLevel.INFO, "STARTUP_DEBUG", $"Tokens Object Present: {tokens != null}");
        if (tokens != null)
        {
            _logger.Log(LogLevel.INFO, "STARTUP_DEBUG", $"Access Token Present: {!string.IsNullOrEmpty(tokens.AccessToken)} (Value: {tokens.AccessToken?.Substring(0, Math.Min(5, tokens.AccessToken?.Length ?? 0))}...)");
            _logger.Log(LogLevel.INFO, "STARTUP_DEBUG", $"Refresh Token Present: {!string.IsNullOrEmpty(tokens.RefreshToken)}");
            _logger.Log(LogLevel.INFO, "STARTUP_DEBUG", $"Parsed Expiry (Raw): {tokens.ExpiresAt:O}");
            _logger.Log(LogLevel.INFO, "STARTUP_DEBUG", $"Calculated Expiry threshold (+72h): {tokens.ExpiresAt.AddHours(72):O}");
            _logger.Log(LogLevel.INFO, "STARTUP_DEBUG", $"Current UTC Time: {DateTimeOffset.UtcNow:O}");
        }

        if (!_authService.IsAuthenticated)
        {
            _logger.Log(LogLevel.INFO, "AUTH", "No valid authentication state found -> Login");
            _logger.Log(LogLevel.INFO, "STARTUP_DEBUG", "Decision: Session Invalid (IsAuthenticated is false).");
            SetNavigationState(NavigationState.Login);
            return;
        }

        if (tokens != null && DateTimeOffset.UtcNow > tokens.ExpiresAt.AddHours(72))
        {
            _logger.Log(LogLevel.WARN, "AUTH", "Offline grace period (72 hours) expired -> Login");
            _logger.Log(LogLevel.INFO, "STARTUP_DEBUG", "Decision: Session Invalid (Grace period expired). Calling ClearTokens() (which clears session/files).");
            _tokenService.ClearTokens();
            SetNavigationState(NavigationState.Login);
            return;
        }

        bool active = await _heartbeatService.CheckImmediateAsync();
        if (!active)
        {
            _logger.Log(LogLevel.WARN, "AUTH", "Device presence check failed on startup (device removed) -> Login");
            _tokenService.ClearTokens();
            SetNavigationState(NavigationState.Login);
            ShowError("This device has been removed from your account.");
            return;
        }
        
        _logger.Log(LogLevel.INFO, "STARTUP_DEBUG", "Decision: Session Valid. Proceeding to main navigation.");
        _ = RefreshJwtSafelyAsync();
        _ = RefreshProfileSafelyAsync();

        _logger.Log(LogLevel.INFO, "NAV", "Authenticated -> Main");
        SetNavigationState(NavigationState.Main);
        _ = UpdateDashboardAsync();
        StartDeviceHeartbeat();
    }

    private void StartDeviceHeartbeat()
    {
        _heartbeatService.Start(() =>
        {
            DispatcherQueue.TryEnqueue(() =>
            {
                _logger.Log(LogLevel.WARN, "NAV", "Device presence heartbeat revoked -> Logout");
                _sessionManager.StopSession();
                _tokenService.ClearTokens();
                SetNavigationState(NavigationState.Login);
                ShowError("This device has been removed from your account.");
            });
        });
    }

    private async Task RefreshJwtSafelyAsync()
    {
        try { await _authService.RefreshTokenIfNeededAsync(); }
        catch (Exception ex) { _logger.Log(LogLevel.WARN, "AUTH", $"JWT refresh attempt failed offline: {ex.Message}"); }
    }

    private async Task RefreshProfileSafelyAsync()
    {
        try { await _configProvider.RefreshProfileBackgroundAsync(); }
        catch (Exception ex) { _logger.Log(LogLevel.WARN, "CONFIG", $"Background profile refresh failed: {ex.Message}"); }
    }

    public async Task HandleActivationUriAsync(string uriOrArgs)
    {
        if (!await _activationLock.WaitAsync(0))
        {
            _logger.Log(LogLevel.WARN, "DEEP_LINK", "Concurrent deep link activation ignored");
            return;
        }
        try
        {
            _logger.Log(LogLevel.INFO, "DEEP_LINK", "Processing activation URI/arguments");
            string exchangeToken = "";
            var parts = uriOrArgs.Split(new[] { '?', '&' }, StringSplitOptions.RemoveEmptyEntries);
            foreach (var part in parts)
            {
                if (part.StartsWith("exchange_token=", StringComparison.OrdinalIgnoreCase))
                {
                    exchangeToken = Uri.UnescapeDataString(part.Substring("exchange_token=".Length));
                    break;
                }
            }

            if (string.IsNullOrWhiteSpace(exchangeToken))
            {
                _logger.Log(LogLevel.WARN, "DEEP_LINK", "No exchange_token found in activation string");
                return;
            }

            string deviceGuid = _authService.GetOrCreateDeviceGuid();
            var result = await _oracleClient.ExchangeTokenAsync(exchangeToken, deviceGuid);
            if (result.Success && result.Tokens != null)
            {
                _logger.Log(LogLevel.INFO, "AUTH", "Exchange token redemption successful");
                bool remember = RememberDeviceCheckBox.IsChecked ?? true;
                if (remember)
                {
                    _tokenService.UpdateTokens(result.Tokens);
                }
                else
                {
                    _tokenService.UpdateTokensInMemoryOnly(result.Tokens);
                }

                var currentVersion = System.Reflection.Assembly.GetExecutingAssembly().GetName().Version ?? new Version(1, 0, 0);
                if (currentVersion < MinimumSupportedVersion)
                {
                    _logger.Log(LogLevel.ERROR, "AUTH", "Client version below MinimumSupportedVersion -> Blocked");
                    SetNavigationState(NavigationState.Login);
                    ShowError("Your client version is outdated. Please update to continue.");
                    return;
                }

                SetNavigationState(NavigationState.Main);
            }
            else
            {
                _logger.Log(LogLevel.ERROR, "AUTH", $"Exchange token redemption failed: {result.ErrorMessage}");
                _tokenService.ClearTokens();
                SetNavigationState(NavigationState.Login);
                ShowError("Authentication link invalid or expired. Please log in manually.");
            }
        }
        catch (Exception ex)
        {
            _logger.Log(LogLevel.ERROR, "DEEP_LINK", $"Activation error: {ex.Message}");
            SetNavigationState(NavigationState.Login);
        }
        finally
        {
            _activationLock.Release();
        }
    }

    private void SetNavigationState(NavigationState state)
    {
        GlobalErrorBanner.IsOpen = false;
        SplashPanel.Visibility = Visibility.Collapsed;
        LoginPanel.Visibility = Visibility.Collapsed;
        DashboardPanel.Visibility = Visibility.Collapsed;
        SettingsPanel.Visibility = Visibility.Collapsed;
        SaveMasterTokenPanel.Visibility = Visibility.Collapsed;

        switch (state)
        {
            case NavigationState.Splash: SplashPanel.Visibility = Visibility.Visible; break;
            case NavigationState.Login: LoginPanel.Visibility = Visibility.Visible; break;
            case NavigationState.Main: DashboardPanel.Visibility = Visibility.Visible; break;
            case NavigationState.Settings: SettingsPanel.Visibility = Visibility.Visible; break;
            case NavigationState.FirstTimeMasterToken: SaveMasterTokenPanel.Visibility = Visibility.Visible; break;
        }
    }

    private void SaveMasterTokenDone_Click(object sender, RoutedEventArgs e)
    {
        SetNavigationState(NavigationState.Main);
        _ = UpdateDashboardAsync();
    }

    private void SessionManager_OnStateChanged(string stateLabel)
    {
        DispatcherQueue.TryEnqueue(() =>
        {
            Color orbColor = stateLabel switch
            {
                "Connected" => Green,
                "Connecting\u2026" => Orange,
                _ => Gray
            };
            SetState(stateLabel, orbColor, stateLabel == "Connected" ? "" : TimerLabel.Text);
        });
    }

    private void SessionManager_OnConnectedChanged(bool connected)
    {
        DispatcherQueue.TryEnqueue(() =>
        {
            if (connected)
            {
                _connectedAt = DateTime.Now;
                _timer.Start();
                _tray.SetConnected(true);
                TimerLabel.Visibility = Visibility.Visible;
                _ = FetchExitIpAsync();
            }
            else
            {
                _timer.Stop();
                TimerLabel.Visibility = Visibility.Collapsed;
                ExitIpLabel.Text = "\u2014";
                RetryLabel.Text  = "\u2014";
                _tray.SetConnected(false);
            }

            ConnectButton.Visibility = connected ? Visibility.Collapsed : Visibility.Visible;
            DisconnectButton.Visibility = connected ? Visibility.Visible : Visibility.Collapsed;
            ConnectButton.IsEnabled = !connected;
            DisconnectButton.IsEnabled = connected;
        });
    }

    private void SessionManager_OnRetryUpdate(string retryText)
    {
        DispatcherQueue.TryEnqueue(() => RetryLabel.Text = retryText);
    }

    private void SessionManager_OnError(string errorMsg)
    {
        DispatcherQueue.TryEnqueue(() => ShowError($"Connection Error: {errorMsg}"));
    }

    private async void LoginActionBtn_Click(object sender, RoutedEventArgs e)
    {
        string credential = CredentialBox.Password.Trim();
        StartupLogger.LogAuth($"[UI] Login button clicked. Credential length={credential.Length}");

        if (string.IsNullOrEmpty(credential))
        {
            ShowError("Please enter your Stealthy Credential.");
            return;
        }

        LoginActionBtn.IsEnabled = false;
        GlobalErrorBanner.IsOpen = false;
        _logger.Log(LogLevel.INFO, "AUTH", "Manual login attempt initiated");
        try
        {
            StartupLogger.LogAuth("[UI] Calling _authService.LoginAsync(credential)...");
            var result = await _authService.LoginAsync(credential);
            StartupLogger.LogAuth($"[UI] _authService.LoginAsync returned Status={result.Status}, ErrorMessage={result.ErrorMessage}");
            HandleLoginResult(result);
        }
        catch (Exception ex)
        {
            StartupLogger.LogAuth($"[UI] Exception in LoginActionBtn_Click: {ex}");
            _logger.Log(LogLevel.ERROR, "AUTH", $"Connection error: {ex.Message}");
            ShowError("Connection error: " + ex.Message);
        }
        finally
        {
            LoginActionBtn.IsEnabled = true;
        }
    }

    private async void Verify2FaBtn_Click(object sender, RoutedEventArgs e)
    {
        string credential = CredentialBox.Password.Trim();
        string totp = TotpBox.Text.Trim();
        StartupLogger.LogAuth($"[UI] Verify 2FA button clicked. Credential length={credential.Length}, TOTP length={totp.Length}");

        if (string.IsNullOrEmpty(totp))
        {
            ShowError("Please enter your 2FA code.");
            return;
        }

        Verify2FaBtn.IsEnabled = false;
        GlobalErrorBanner.IsOpen = false;
        try
        {
            StartupLogger.LogAuth("[UI] Calling _authService.LoginAsync(credential, totp)...");
            var result = await _authService.LoginAsync(credential, totp);
            StartupLogger.LogAuth($"[UI] _authService.LoginAsync(totp) returned Status={result.Status}, ErrorMessage={result.ErrorMessage}");
            HandleLoginResult(result);
        }
        catch (Exception ex)
        {
            StartupLogger.LogAuth($"[UI] Exception in Verify2FaBtn_Click: {ex}");
            _logger.Log(LogLevel.ERROR, "AUTH", $"2FA error: {ex.Message}");
            ShowError("Connection error: " + ex.Message);
        }
        finally
        {
            Verify2FaBtn.IsEnabled = true;
        }
    }

    private void HandleLoginResult(LoginResult result)
    {
        if (result.Status == LoginStatus.Success && result.Tokens != null)
        {
            if (RememberDeviceCheckBox.IsChecked != true)
            {
                _tokenService.UpdateTokensInMemoryOnly(result.Tokens);
            }
            
            var currentVersion = System.Reflection.Assembly.GetExecutingAssembly().GetName().Version ?? new Version(1, 0, 0);
            if (currentVersion < MinimumSupportedVersion)
            {
                _logger.Log(LogLevel.ERROR, "AUTH", "Client version below MinimumSupportedVersion -> Blocked");
                ShowError("Your client version is outdated. Please download the latest update.");
                return;
            }

            _logger.Log(LogLevel.INFO, "NAV", "Login success -> Main");
            TwoFaPanel.Visibility = Visibility.Collapsed;
            SetNavigationState(NavigationState.Main);
            _ = UpdateDashboardAsync();
            StartDeviceHeartbeat();
        }
        else if (result.Status == LoginStatus.SubscriptionExpired)
        {
            _logger.Log(LogLevel.WARN, "AUTH", "Subscription expired");
            ShowError("Your VPN subscription has expired. Please renew to continue using the service.");
            _ = Windows.System.Launcher.LaunchUriAsync(new Uri("https://stealthy.co.in/account/billing"));
        }
        else if (result.Status == LoginStatus.MandatoryUpdate)
        {
            _logger.Log(LogLevel.ERROR, "AUTH", "Mandatory update required");
            ShowError("A critical security update is required to connect.");
            _ = Windows.System.Launcher.LaunchUriAsync(new Uri("https://stealthy.co.in/download"));
        }
        else if (result.Status == LoginStatus.MaintenanceMode)
        {
            _logger.Log(LogLevel.WARN, "AUTH", "Service in maintenance mode");
            string detail = result.RetryAfterSeconds.HasValue 
                ? $"The service is undergoing scheduled maintenance. Please try again in {result.RetryAfterSeconds} seconds."
                : "The service is undergoing scheduled maintenance. Please try again later.";
            ShowError(detail);
        }
        else if (result.Status == LoginStatus.Requires2FA)
        {
            TwoFaPanel.Visibility = Visibility.Visible;
            LoginActionBtn.Visibility = Visibility.Collapsed;
        }
        else if (result.Status == LoginStatus.DeviceLimitExceeded)
        {
            var details = result.DeviceLimitDetails;
            string msg = details != null 
                ? $"You have reached your device limit ({details.CurrentDevices} / {details.MaxDevices}). Please remove a device to continue."
                : "You have reached your device limit. Please remove a device to continue.";
            ShowError(msg);
            _ = Windows.System.Launcher.LaunchUriAsync(new Uri(details?.ManageDevicesUrl ?? "https://stealthy.co.in/account"));
        }
        else if (result.Status == LoginStatus.DeviceOwnershipError)
        {
            _logger.Log(LogLevel.ERROR, "AUTH", "Device ownership conflict");
            ShowError(result.ErrorMessage ?? "This device is already registered to another account.");
        }
        else if (result.Status == LoginStatus.DeviceDeactivated)
        {
            _logger.Log(LogLevel.ERROR, "AUTH", "Device deactivated");
            ShowError(result.ErrorMessage ?? "This device has been deactivated. Please reactivate or remove it in your account portal.");
        }
        else if (result.Status == LoginStatus.AccountDisabled)
        {
            _logger.Log(LogLevel.ERROR, "AUTH", "Account disabled");
            ShowError(result.ErrorMessage ?? "Your account has been disabled or is inactive.");
        }
        else if (result.Status == LoginStatus.InvalidMasterToken)
        {
            _logger.Log(LogLevel.ERROR, "AUTH", "Invalid credentials");
            ShowError(result.ErrorMessage ?? "Invalid Account ID or Master Token.");
        }
        else if (result.Status == LoginStatus.ReplayDetected)
        {
            _logger.Log(LogLevel.WARN, "AUTH", "Replay detected -> Terminating session");
            _authService.Logout();
            ShowError("Security Alert: A potential replay attack was detected. Your session has been terminated.");
        }
        else
        {
            ShowError(result.ErrorMessage ?? "Login failed.");
        }
    }

    private void GoToSettings_Click(object sender, RoutedEventArgs e)
    {
        SetNavigationState(NavigationState.Settings);
    }

    private void BackToMain_Click(object sender, RoutedEventArgs e)
    {
        SetNavigationState(NavigationState.Main);
    }

    private async Task UpdateDashboardAsync()
    {
        var token = await _authService.GetValidAccessTokenAsync();
        if (string.IsNullOrEmpty(token))
        {
            DispatcherQueue.TryEnqueue(() => {
                ProfileApiConnectivityText.Text = "Offline (No Token)";
                DebugApiReachabilityText.Text = "API Reachability: Offline";
            });
            return;
        }
        
        try
        {
            var me = await _oracleClient.FetchClientMeAsync(token);
            if (me != null)
            {
                DispatcherQueue.TryEnqueue(() => {
                    ProfilePlanText.Text = me.Plan;
                    ProfileDevicesText.Text = $"{me.DeviceCount}";
                    Profile2FaText.Text = me.TwoFactorEnabled ? "Enabled" : "Disabled";
                    ProfileApiConnectivityText.Text = "Online";
                    
                    DebugApiReachabilityText.Text = "API Reachability: \u2713 Online";
                });
            }
        }
        catch (Exception ex)
        {
            DispatcherQueue.TryEnqueue(() => {
                ProfileApiConnectivityText.Text = "Offline / Error";
                DebugApiReachabilityText.Text = $"API Reachability: Error ({ex.Message})";
            });
        }

        DispatcherQueue.TryEnqueue(() => {
            var t = _tokenService.CurrentTokens;
            if (t != null)
            {
                var jwtExpiry = t.ExpiresAt - DateTimeOffset.UtcNow;
                DebugJwtExpiryText.Text = $"JWT expires in: {(int)jwtExpiry.TotalMinutes} min";
            }
            
            string apiBaseUrl = Environment.GetEnvironmentVariable("STEALTHY_API_URL") ?? "https://api.stealthy.co.in";
            DebugBackendText.Text = $"Backend: {apiBaseUrl}";
            DebugVersionText.Text = $"Version: {System.Reflection.Assembly.GetExecutingAssembly().GetName().Version}";
            DebugGitCommitText.Text = "Git Commit: Local Build";
        });
    }

    private void ManageDevices_Click(object sender, RoutedEventArgs e)
    {
        _ = Windows.System.Launcher.LaunchUriAsync(new Uri("https://stealthy.co.in/account"));
    }

    private void Logout_Click(object sender, RoutedEventArgs e)
    {
        _heartbeatService.Stop();
        _sessionManager.StopSession();
        _tokenService.ClearTokens();
        CredentialBox.Password = "";
        TotpBox.Text = "";
        TwoFaPanel.Visibility = Visibility.Collapsed;
        LoginActionBtn.Visibility = Visibility.Visible;
        SetNavigationState(NavigationState.Login);
    }

    private async void ConnectButton_Click(object sender, RoutedEventArgs e)
    {
        ExitIpLabel.Text = "\u2014";
        await _sessionManager.StartSessionAsync();
    }

    private void DisconnectButton_Click(object sender, RoutedEventArgs e) => Disconnect();

    internal void DisconnectFromTray() => Disconnect();

    private void Disconnect()
    {
        _sessionManager.StopSession();
    }

    private void ApplyTheme()
    {
        if (_settings.Theme == "Dark")
            RootGrid.RequestedTheme = ElementTheme.Dark;
        else if (_settings.Theme == "Light")
            RootGrid.RequestedTheme = ElementTheme.Light;
        else
            RootGrid.RequestedTheme = ElementTheme.Default;

        foreach (ComboBoxItem item in ThemeComboBox.Items)
        {
            if (item.Tag?.ToString() == _settings.Theme)
            {
                ThemeComboBox.SelectedItem = item;
                break;
            }
        }
    }

    private void ThemeComboBox_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (ThemeComboBox.SelectedItem is ComboBoxItem item)
        {
            string theme = item.Tag?.ToString() ?? "System";
            _settings.Theme = theme;
            _settings.Save();
            ApplyTheme();
        }
    }

    private void MainWindow_SizeChanged(object sender, WindowSizeChangedEventArgs args)
    {
        // Enforce 900x650 minimum
        if (args.Size.Width < 900 || args.Size.Height < 650)
        {
            AppWindow.Resize(new SizeInt32(
                Math.Max(900, (int)args.Size.Width), 
                Math.Max(650, (int)args.Size.Height)));
        }
    }

    private void SetState(string label, Color orb, string timer)
    {
        StatusLabel.Text = label;
        TimerLabel.Text  = timer;
        StatusIcon.Foreground = new SolidColorBrush(orb);
        StatusOrbGlow.Fill    = new SolidColorBrush(Color.FromArgb(60, orb.R, orb.G, orb.B));
    }

    private void Timer_Tick(object? sender, object e)
        => TimerLabel.Text = (DateTime.Now - _connectedAt).ToString(@"hh\:mm\:ss");

    private async Task FetchExitIpAsync()
    {
        try
        {
            ExitIpLabel.Text = "\u2026";
            ExitIpLabel.Text = (await _http.GetStringAsync("https://ifconfig.me/ip")).Trim();
        }
        catch { ExitIpLabel.Text = "?"; }
    }

    private void TitleBar_PointerPressed(object sender, PointerRoutedEventArgs e)
    {
        var hWnd = WinRT.Interop.WindowNative.GetWindowHandle(this);
        ReleaseCapture();
        PostMessage(hWnd, WM_NCLBUTTONDOWN, (IntPtr)HTCAPTION, IntPtr.Zero);
    }

    private void MinimiseButton_Click(object sender, RoutedEventArgs e)
    {
        AppWindow.Hide();
        _tray.ShowBalloon("Stealthy running in tray");
    }

    private void OnClosed(object sender, WindowEventArgs args)
    {
        // Save window bounds before minimizing/closing
        _settings.WindowWidth = AppWindow.Size.Width;
        _settings.WindowHeight = AppWindow.Size.Height;
        _settings.Save();

        args.Handled = true;
        AppWindow.Hide();
        _tray.ShowBalloon("Stealthy running in tray");
    }

    internal void ShowFromTray()
    {
        AppWindow.Show();
        AppWindow.SetPresenter(AppWindowPresenterKind.Overlapped);
    }

    internal void ExitApp()
    {
        _heartbeatService.Stop();
        _sessionManager.StopSession();
        _tray.Dispose();
        Application.Current.Exit();
    }

    private void ShowError(string msg)
    {
        GlobalErrorBanner.Message = msg;
        GlobalErrorBanner.IsOpen = true;
    }
}
