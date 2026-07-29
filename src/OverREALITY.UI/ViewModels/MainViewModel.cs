using System.Threading.Tasks;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using MaterialDesignThemes.Wpf;
using OverREALITY.Shared.Interfaces;
using OverREALITY.UI.Services;

namespace OverREALITY.UI.ViewModels;

public partial class MainViewModel : ObservableObject
{
    public INavigationService Navigation { get; }
    private readonly ISessionManager _sessionManager;
    private readonly ISettingsService _settingsService;
    private readonly IConnectionService _connectionService;
    private readonly IAuthService _authService;
    private readonly IApiClient _apiClient;
    private System.Windows.Threading.DispatcherTimer? _heartbeatTimer;

    public MainViewModel(
        INavigationService navigationService, 
        ISessionManager sessionManager, 
        ISettingsService settingsService,
        IConnectionService connectionService,
        IAuthService authService,
        IApiClient apiClient)
    {
        Navigation = navigationService;
        _sessionManager = sessionManager;
        _settingsService = settingsService;
        _connectionService = connectionService;
        _authService = authService;
        _apiClient = apiClient;
        
        _sessionManager.SessionChanged += OnSessionChanged;

        ApplyInitialTheme();
        _ = InitializeAsync();
    }

    private void OnSessionChanged(object? sender, OverREALITY.Shared.Domain.Session.SessionChangedEventArgs e)
    {
        if (e.NewSession == null)
        {
            _heartbeatTimer?.Stop();
            App.Current.Dispatcher.Invoke(() => Navigation.NavigateTo<LoginViewModel>());
        }
        else
        {
            StartHeartbeat();
        }
    }

    private void StartHeartbeat()
    {
        if (_heartbeatTimer == null)
        {
            _heartbeatTimer = new System.Windows.Threading.DispatcherTimer
            {
                Interval = System.TimeSpan.FromSeconds(30)
            };
            _heartbeatTimer.Tick += async (s, e) => await CheckHeartbeatAsync();
        }
        _heartbeatTimer.Start();
    }

    private async Task CheckHeartbeatAsync()
    {
        if (_sessionManager.CurrentSession != null)
        {
            var result = await _apiClient.GetAsync<OverREALITY.Shared.Api.DeviceStatusResponse>("/api/devices/status");
            if (result.IsSuccess && result.Value != null && !result.Value.Active)
            {
                await _authService.LogoutAsync();
            }
        }
    }

    private void ApplyInitialTheme()
    {
        var themeName = _settingsService.Settings.Theme;
        var paletteHelper = new MaterialDesignThemes.Wpf.PaletteHelper();
        var theme = paletteHelper.GetTheme();
        theme.SetBaseTheme(themeName == "Dark" ? MaterialDesignThemes.Wpf.Theme.Dark : MaterialDesignThemes.Wpf.Theme.Light);
        paletteHelper.SetTheme(theme);
    }

    private async Task InitializeAsync()
    {
        if (await _authService.TryRestoreSessionAsync())
        {
            var statusResult = await _apiClient.GetAsync<OverREALITY.Shared.Api.DeviceStatusResponse>("/api/devices/status");
            if (!statusResult.IsSuccess && (statusResult.Error?.Code == "Unauthorized" || statusResult.Error?.Code == "Forbidden"))
            {
                await _authService.LogoutAsync();
                return;
            }
            
            if (statusResult.IsSuccess && statusResult.Value != null && !statusResult.Value.Active)
            {
                await _authService.LogoutAsync();
                return;
            }

            StartHeartbeat();
            Navigation.NavigateTo<DashboardViewModel>();
            if (_settingsService.Settings.AutoConnect)
            {
                _ = _connectionService.ConnectAsync();
            }
        }
        else
        {
            Navigation.NavigateTo<LoginViewModel>();
        }
    }

    [RelayCommand]
    private void NavigateDashboard()
    {
        if (Navigation.CurrentView is not LoginViewModel)
            Navigation.NavigateTo<DashboardViewModel>();
    }

    [RelayCommand]
    private void NavigateLogs()
    {
        if (Navigation.CurrentView is not LoginViewModel)
            Navigation.NavigateTo<LogsViewModel>();
    }

    [RelayCommand]
    private void NavigateSettings()
    {
        if (Navigation.CurrentView is not LoginViewModel)
            Navigation.NavigateTo<SettingsViewModel>();
    }
}
