using System.Threading.Tasks;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using RealityTunnel.OperationsConsole.Services;
using RealityTunnel.OperationsConsole.Shared;

namespace RealityTunnel.OperationsConsole.ViewModels
{
    public partial class LoginViewModel : ObservableObject
    {
        private readonly IAdminApiService _apiService;
        private readonly ISessionService _sessionService;
        private readonly INavigationService _navigationService;
        private readonly IDialogService _dialogService;

        [ObservableProperty]
        private string username = string.Empty;

        [ObservableProperty]
        private string password = string.Empty;

        [ObservableProperty]
        private string serverUrl = "https://api.stealthy.co.in";

        [ObservableProperty]
        private bool isBusy;

        [ObservableProperty]
        private string errorMessage = string.Empty;

        public LoginViewModel(
            IAdminApiService apiService,
            ISessionService sessionService,
            INavigationService navigationService,
            IDialogService dialogService)
        {
            _apiService = apiService;
            _sessionService = sessionService;
            _navigationService = navigationService;
            _dialogService = dialogService;
            ServerUrl = _sessionService.ServerBaseUrl;
        }

        [RelayCommand]
        private async Task LoginAsync()
        {
            ErrorMessage = string.Empty;

            if (string.IsNullOrWhiteSpace(Username) || string.IsNullOrWhiteSpace(Password))
            {
                ErrorMessage = "Please enter both username and password.";
                return;
            }

            IsBusy = true;
            try
            {
                _sessionService.ServerBaseUrl = ServerUrl;
                var request = new AdminLoginRequest
                {
                    Username = Username.Trim(),
                    Password = Password
                };

                var result = await _apiService.PostAsync<AdminLoginResponse, AdminLoginRequest>(ApiRoutes.Admin.Login, request);

                if (result.IsSuccess && result.Data != null)
                {
                    // Store memory-only session
                    _sessionService.SetSession(result.Data.AccessToken, result.Data.Username, result.Data.Role);

                    // Clear sensitive fields locally
                    Password = string.Empty;

                    // Navigate to main console window
                    _navigationService.ShowMainWindow();
                }
                else
                {
                    ErrorMessage = result.ErrorMessage ?? "Login failed. Please verify credentials.";
                }
            }
            finally
            {
                IsBusy = false;
            }
        }
    }
}
