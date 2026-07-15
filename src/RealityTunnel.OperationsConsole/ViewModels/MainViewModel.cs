using System;
using System.Threading.Tasks;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using RealityTunnel.OperationsConsole.Services;
using RealityTunnel.OperationsConsole.Shared;

namespace RealityTunnel.OperationsConsole.ViewModels
{
    public partial class MainViewModel : ObservableObject, IDisposable
    {
        private readonly ISessionService _sessionService;
        private readonly INavigationService _navigationService;
        private readonly IAdminApiService _apiService;
        private readonly IDialogService _dialogService;

        [ObservableProperty]
        private string currentUsername = string.Empty;

        [ObservableProperty]
        private string currentRole = string.Empty;

        [ObservableProperty]
        private bool isSuperAdmin;

        [ObservableProperty]
        private string currentViewTitle = "Dashboard";

        [ObservableProperty]
        private object? currentViewContent;

        [ObservableProperty]
        private int selectedNavIndex = 0;

        public MainViewModel(
            ISessionService sessionService,
            INavigationService navigationService,
            IAdminApiService apiService,
            IDialogService dialogService)
        {
            _sessionService = sessionService;
            _navigationService = navigationService;
            _apiService = apiService;
            _dialogService = dialogService;

            _sessionService.SessionExpired += OnSessionExpired;
            _navigationService.OnNavigate += OnNavigateToView;
        }

        public void Initialize()
        {
            CurrentUsername = _sessionService.CurrentUsername;
            CurrentRole = _sessionService.CurrentRole;
            IsSuperAdmin = CurrentRole.Equals("super_admin", StringComparison.OrdinalIgnoreCase);

            // Fetch latest profile via GET /api/admin/me
            _ = LoadProfileAsync();

            // Default view to Dashboard
            NavigateCommand.Execute("Dashboard");
        }

        private async Task LoadProfileAsync()
        {
            var res = await _apiService.GetAsync<AdminProfileResponse>(ApiRoutes.Admin.Me);
            if (res.IsSuccess && res.Data != null)
            {
                CurrentUsername = res.Data.Username;
                IsSuperAdmin = res.Data.IsSuperAdmin;
                CurrentRole = res.Data.IsSuperAdmin ? "Super Admin" : "Admin";
            }
        }

        [RelayCommand]
        private void Navigate(string viewKey)
        {
            _navigationService.NavigateTo(viewKey);
        }

        private void OnNavigateToView(string viewKey, object? parameter)
        {
            CurrentViewTitle = viewKey switch
            {
                "Dashboard" => "Operational Dashboard",
                "Users" => "Customer Accounts & Provisioning",
                "UserDetails" => "Account Details & Management",
                "Subscriptions" => "Subscriptions Management",
                "Payments" => "Payments & Reconciliations",
                "Infrastructure" => "System Health & Infrastructure",
                "Logs" => "System & Action Logs",
                "Settings" => "Console Settings & Server Diagnostics",
                _ => viewKey
            };
        }

        [RelayCommand]
        private async Task LogoutAsync()
        {
            bool confirm = await _dialogService.ShowConfirmationAsync("Confirm Logout", "Are you sure you want to log out? Any memory-only session tokens will be purged immediately.");
            if (confirm)
            {
                _sessionService.ClearSession();
                _navigationService.ShowLoginWindow();
            }
        }

        private void OnSessionExpired(object? sender, EventArgs e)
        {
            _ = _dialogService.ShowInfoAsync("Session Expired", "Your session has expired due to 10 minutes of inactivity. Please log in again.");
            _navigationService.ShowLoginWindow();
        }

        public void Dispose()
        {
            _sessionService.SessionExpired -= OnSessionExpired;
            _navigationService.OnNavigate -= OnNavigateToView;
            GC.SuppressFinalize(this);
        }
    }
}
