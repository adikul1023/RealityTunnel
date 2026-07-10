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

public enum NavigationState { Splash, Login, Main, Profile, FirstTimeMasterToken }

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
        OracleApiClient oracleClient)
    {
        InitializeComponent();
        _sessionManager = sessionManager;
        _authService = authService;
        _configProvider = configProvider;
        _tokenService = tokenService;
        _licenseService = licenseService;
        _logger = logger;
        _oracleClient = oracleClient;
        _tray = new TrayIcon(this);

        // Compact floating window — no title bar chrome, always on top
        var appWin = AppWindow;
        appWin.Resize(new SizeInt32(260, 420));
        if (appWin.Presenter is OverlappedPresenter p)
        {
            p.IsResizable    = false;
            p.IsMaximizable  = false;
            p.IsAlwaysOnTop  = true;
        }
        ExtendsContentIntoTitleBar = true;

        // Set taskbar / title-bar icon
        string? exeDir = System.IO.Path.GetDirectoryName(Environment.ProcessPath);
        string iconPath = System.IO.Path.Combine(exeDir ?? AppContext.BaseDirectory, "app.ico");
        if (System.IO.File.Exists(iconPath))
            AppWindow.SetIcon(iconPath);

        _timer.Tick += Timer_Tick;

        _sessionManager.OnStateChanged += SessionManager_OnStateChanged;
        _sessionManager.OnConnectedChanged += SessionManager_OnConnectedChanged;
        _sessionManager.OnRetryUpdate += SessionManager_OnRetryUpdate;

        ServerIpTextBox.Text = _settings.ServerIp;
        this.Closed += OnClosed;

        _ = RunStartupSequenceAsync();
    }

    private static readonly Version MinimumSupportedVersion = new(1, 0, 0);

    private async Task RunStartupSequenceAsync()
    {
        _logger.Log(LogLevel.INFO, "STARTUP", "Starting explicit 6-step client initialization sequence");
        SetNavigationState(NavigationState.Splash);

        // 1. Load cached credentials
        // 2. Load cached VPN profile
        var profile = _configProvider.GetCachedProfile();

        // 3. Validate offline license
        if (!_authService.IsAuthenticated)
        {
            _logger.Log(LogLevel.INFO, "AUTH", "No valid authentication state found -> Login");
            SetNavigationState(NavigationState.Login);
            return;
        }

        var tokens = _tokenService.CurrentTokens;
        if (tokens != null && DateTimeOffset.UtcNow > tokens.ExpiresAt.AddHours(72))
        {
            _logger.Log(LogLevel.WARN, "AUTH", "Offline grace period (72 hours) expired -> Login");
            _tokenService.ClearTokens();
            SetNavigationState(NavigationState.Login);
            return;
        }
        // 4 & 5. Refresh JWT and Profile asynchronously without blocking UI
        _ = RefreshJwtSafelyAsync();
        _ = RefreshProfileSafelyAsync();

        // 6. Navigate with auto-recovery for missing cached profile
        if (profile == null)
        {
            _logger.Log(LogLevel.WARN, "CONFIG", "Cached profile missing -> attempting network recovery");
            profile = await _configProvider.GetVpnProfileAsync();
        }

        if (profile != null)
        {
            _logger.Log(LogLevel.INFO, "NAV", "Authenticated and profile available -> Main");
            SetNavigationState(NavigationState.Main);
            ServerIpTextBox.Text = profile.ServerIp;
        }
        else
        {
            SetNavigationState(NavigationState.Login);
        }
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

                // Version compatibility check after online authentication
                var currentVersion = System.Reflection.Assembly.GetExecutingAssembly().GetName().Version ?? new Version(1, 0, 0);
                if (currentVersion < MinimumSupportedVersion)
                {
                    _logger.Log(LogLevel.ERROR, "AUTH", "Client version below MinimumSupportedVersion -> Blocked");
                    SetNavigationState(NavigationState.Login);
                    await ShowError("Your client version is outdated. Please update to continue.");
                    return;
                }

                // Never display Master Token — proceed to authenticated experience
                SetNavigationState(NavigationState.Main);
            }
            else
            {
                _logger.Log(LogLevel.ERROR, "AUTH", $"Exchange token redemption failed: {result.ErrorMessage}");
                _tokenService.ClearTokens();
                SetNavigationState(NavigationState.Login);
                await ShowError("Authentication link invalid or expired. Please log in manually.");
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
        SplashPanel.Visibility = Visibility.Collapsed;
        LoginPanel.Visibility = Visibility.Collapsed;
        MainVpnPanel.Visibility = Visibility.Collapsed;
        ProfilePanel.Visibility = Visibility.Collapsed;
        SaveMasterTokenPanel.Visibility = Visibility.Collapsed;

        switch (state)
        {
            case NavigationState.Splash: SplashPanel.Visibility = Visibility.Visible; break;
            case NavigationState.Login: LoginPanel.Visibility = Visibility.Visible; break;
            case NavigationState.Main: MainVpnPanel.Visibility = Visibility.Visible; break;
            case NavigationState.Profile: ProfilePanel.Visibility = Visibility.Visible; break;
            case NavigationState.FirstTimeMasterToken: SaveMasterTokenPanel.Visibility = Visibility.Visible; break;
        }
    }

    private void SaveMasterTokenDone_Click(object sender, RoutedEventArgs e)
    {
        SetNavigationState(NavigationState.Main);
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
                _ = FetchExitIpAsync();
            }
            else
            {
                _timer.Stop();
                ExitIpLabel.Text = "\u2014";
                RetryLabel.Text  = "\u2014";
                _tray.SetConnected(false);
            }

            ConnectButton.IsEnabled = !connected;
            DisconnectButton.IsEnabled = connected;
            ServerIpTextBox.IsEnabled = !connected;
        });
    }

    private void SessionManager_OnRetryUpdate(string retryText)
    {
        DispatcherQueue.TryEnqueue(() => RetryLabel.Text = retryText);
    }

    private async void LoginActionBtn_Click(object sender, RoutedEventArgs e)
    {
        string accountId = AccountIdBox.Text.Trim();
        string masterToken = MasterTokenBox.Password.Trim();

        if (string.IsNullOrEmpty(accountId) || string.IsNullOrEmpty(masterToken))
        {
            await ShowError("Please enter both Account ID and Master Token.");
            return;
        }

        LoginActionBtn.IsEnabled = false;
        _logger.Log(LogLevel.INFO, "AUTH", "Manual login attempt initiated");
        try
        {
            var result = await _authService.LoginAsync(accountId, masterToken);
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
                    await ShowError("Your client version is outdated. Please download the latest update.");
                    return;
                }

                var profile = await _configProvider.GetVpnProfileAsync();
                if (profile != null)
                {
                    _logger.Log(LogLevel.INFO, "NAV", "Login success -> Main");
                    ServerIpTextBox.Text = profile.ServerIp;
                    SetNavigationState(NavigationState.Main);
                }
                else
                {
                    await ShowError("Failed to fetch VPN configuration.");
                }
            }
            else if (result.Status == LoginStatus.SubscriptionExpired)
            {
                _logger.Log(LogLevel.WARN, "AUTH", "Subscription expired");
                var dialog = new ContentDialog
                {
                    Title = "Subscription Expired",
                    Content = "Your VPN subscription has expired. Please renew to continue using the service.",
                    PrimaryButtonText = "Renew Subscription",
                    CloseButtonText = "Cancel",
                    XamlRoot = Content.XamlRoot
                };
                if (await dialog.ShowAsync() == ContentDialogResult.Primary)
                {
                    _ = Windows.System.Launcher.LaunchUriAsync(new Uri("https://stealthy.co.in/account/billing"));
                }
            }
            else if (result.Status == LoginStatus.MandatoryUpdate)
            {
                _logger.Log(LogLevel.ERROR, "AUTH", "Mandatory update required");
                var dialog = new ContentDialog
                {
                    Title = "Mandatory Update Required",
                    Content = "A critical security update is required to connect.",
                    PrimaryButtonText = "Download Update",
                    CloseButtonText = "Close",
                    XamlRoot = Content.XamlRoot
                };
                if (await dialog.ShowAsync() == ContentDialogResult.Primary)
                {
                    _ = Windows.System.Launcher.LaunchUriAsync(new Uri("https://stealthy.co.in/download"));
                }
            }
            else if (result.Status == LoginStatus.MaintenanceMode)
            {
                _logger.Log(LogLevel.WARN, "AUTH", "Service in maintenance mode");
                string detail = result.RetryAfterSeconds.HasValue 
                    ? $"The service is undergoing scheduled maintenance. Please try again in {result.RetryAfterSeconds} seconds."
                    : "The service is undergoing scheduled maintenance. Please try again later.";
                await ShowError(detail);
            }
            else if (result.Status == LoginStatus.Requires2FA)
            {
                TextBox totpBox = new TextBox { PlaceholderText = "6-digit code" };
                var dialog = new ContentDialog
                {
                    Title = "Two-Factor Authentication",
                    Content = totpBox,
                    PrimaryButtonText = "Verify",
                    CloseButtonText = "Cancel",
                    XamlRoot = Content.XamlRoot
                };

                if (await dialog.ShowAsync() == ContentDialogResult.Primary)
                {
                    bool verified = await _authService.Verify2FaAsync(result.TemporaryLoginToken ?? "", totpBox.Text);
                    if (verified)
                    {
                        var profile = await _configProvider.GetVpnProfileAsync();
                        if (profile != null)
                        {
                            ServerIpTextBox.Text = profile.ServerIp;
                            SetNavigationState(NavigationState.Main);
                        }
                    }
                    else
                    {
                        await ShowError("Invalid 2FA code.");
                    }
                }
            }
            else if (result.Status == LoginStatus.DeviceLimitExceeded)
            {
                var details = result.DeviceLimitDetails;
                string msg = details != null 
                    ? $"You have reached your device limit ({details.CurrentDevices} / {details.MaxDevices}). Please remove a device to continue."
                    : "You have reached your device limit. Please remove a device to continue.";
                var dialog = new ContentDialog
                {
                    Title = "Device Limit Exceeded",
                    Content = msg,
                    PrimaryButtonText = "Manage Devices",
                    CloseButtonText = "Cancel",
                    XamlRoot = Content.XamlRoot
                };
                if (await dialog.ShowAsync() == ContentDialogResult.Primary)
                {
                    _ = Windows.System.Launcher.LaunchUriAsync(new Uri(details?.ManageDevicesUrl ?? "https://stealthy.co.in/account"));
                }
            }
            else if (result.Status == LoginStatus.ReplayDetected)
            {
                _logger.Log(LogLevel.WARN, "AUTH", "Replay detected -> Terminating session");
                _authService.Logout();
                await ShowError("Security Alert: A potential replay attack was detected. Your session has been terminated for your safety. Please log in again.");
            }
            else
            {
                await ShowError(result.ErrorMessage ?? "Login failed.");
            }
        }
        catch (Exception ex)
        {
            _logger.Log(LogLevel.ERROR, "AUTH", $"Connection error: {ex.Message}");
            await ShowError("Connection error: " + ex.Message);
        }
        finally
        {
            LoginActionBtn.IsEnabled = true;
        }
    }

    private void GoToProfile_Click(object sender, RoutedEventArgs e)
    {
        SetNavigationState(NavigationState.Profile);
    }

    private void BackToMain_Click(object sender, RoutedEventArgs e)
    {
        SetNavigationState(NavigationState.Main);
    }

    private void ManageDevices_Click(object sender, RoutedEventArgs e)
    {
        _ = Windows.System.Launcher.LaunchUriAsync(new Uri("https://stealthy.co.in/account"));
    }

    private void Logout_Click(object sender, RoutedEventArgs e)
    {
        _sessionManager.StopSession();
        _authService.Logout();
        SetNavigationState(NavigationState.Login);
    }

    private async void ConnectButton_Click(object sender, RoutedEventArgs e)
    {
        string ip = ServerIpTextBox.Text.Trim();
        if (string.IsNullOrWhiteSpace(ip)) { await ShowError("Enter a server IP."); return; }

        _settings.ServerIp = ip;
        _settings.Save();
        
        ExitIpLabel.Text = "\u2014";
        await _sessionManager.StartSessionAsync(ip);
    }

    private void DisconnectButton_Click(object sender, RoutedEventArgs e) => Disconnect();

    internal void DisconnectFromTray() => Disconnect();

    private void Disconnect()
    {
        _sessionManager.StopSession();
    }

    // ── UI helpers ───────────────────────────────────────────────────────────

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
        args.Handled = true;
        AppWindow.Hide();
        _tray.ShowBalloon("Stealthy running in tray");
    }

    internal void ShowFromTray()
    {
        AppWindow.Show();
        AppWindow.SetPresenter(AppWindowPresenterKind.Overlapped);
        if (AppWindow.Presenter is OverlappedPresenter p)
        {
            p.IsResizable   = false;
            p.IsMaximizable = false;
            p.IsAlwaysOnTop = true;
        }
    }

    internal void ExitApp()
    {
        _sessionManager.StopSession();
        _tray.Dispose();
        Application.Current.Exit();
    }

    private async Task ShowError(string msg)
    {
        var dlg = new ContentDialog
        {
            Title = "Error", Content = msg, CloseButtonText = "OK",
            XamlRoot = Content.XamlRoot
        };
        await dlg.ShowAsync();
    }
}

