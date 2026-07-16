using System;
using System.Diagnostics;
using System.Threading.Tasks;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using RealityTunnel.OperationsConsole.Services;
using RealityTunnel.OperationsConsole.Shared;

namespace RealityTunnel.OperationsConsole.ViewModels
{
    public partial class SettingsViewModel : ObservableObject
    {
        private readonly IAdminApiService _apiService;
        private readonly ISessionService _sessionService;
        private readonly IDialogService _dialogService;

        [ObservableProperty]
        private string serverUrl = string.Empty;

        [ObservableProperty]
        private string currentUsername = string.Empty;

        [ObservableProperty]
        private string currentRole = string.Empty;

        [ObservableProperty]
        private string pingStatus = "Not Checked";

        [ObservableProperty]
        private string pingLatency = "-";

        [ObservableProperty]
        private bool isBusy;

        [ObservableProperty]
        private string currentPassword = string.Empty;

        [ObservableProperty]
        private string newPassword = string.Empty;

        public SettingsViewModel(
            IAdminApiService apiService,
            ISessionService sessionService,
            IDialogService dialogService)
        {
            _apiService = apiService;
            _sessionService = sessionService;
            _dialogService = dialogService;

            ServerUrl = _sessionService.ServerBaseUrl;
            CurrentUsername = _sessionService.CurrentUsername;
            CurrentRole = _sessionService.CurrentRole;
        }

        [RelayCommand]
        private void SaveSettings()
        {
            if (string.IsNullOrWhiteSpace(ServerUrl)) return;
            _sessionService.ServerBaseUrl = ServerUrl.Trim();
            _ = _dialogService.ShowInfoAsync("Saved", $"Server Base URL updated to {_sessionService.ServerBaseUrl}.");
        }

        [RelayCommand]
        private async Task PingServerAsync()
        {
            if (IsBusy) return;
            IsBusy = true;
            PingStatus = "Checking...";
            PingLatency = "-";

            try
            {
                var sw = Stopwatch.StartNew();
                var res = await _apiService.GetAsync<object>(ApiRoutes.Probes.Livez);
                sw.Stop();

                if (res.IsSuccess)
                {
                    PingStatus = "Online (HTTP 200 OK)";
                    PingLatency = $"{sw.ElapsedMilliseconds} ms";
                }
                else
                {
                    PingStatus = $"Error ({res.StatusCode})";
                }
            }
            finally
            {
                IsBusy = false;
            }
        }

        [RelayCommand]
        private async Task ChangePasswordAsync()
        {
            if (IsBusy) return;
            
            if (string.IsNullOrWhiteSpace(CurrentPassword) || string.IsNullOrWhiteSpace(NewPassword))
            {
                await _dialogService.ShowErrorAsync("Validation Error", "Please provide both current and new passwords.");
                return;
            }

            if (NewPassword.Length < 12)
            {
                await _dialogService.ShowErrorAsync("Validation Error", "New password must be at least 12 characters long.");
                return;
            }

            IsBusy = true;
            try
            {
                var payload = new { current_password = CurrentPassword, new_password = NewPassword };
                var res = await _apiService.PostAsync<AdminChangePasswordResponse, object>("/api/admin/change-password", payload);
                
                if (res.IsSuccess && res.Data != null)
                {
                    await _dialogService.ShowInfoAsync("Success", res.Data.Message);
                    CurrentPassword = string.Empty;
                    NewPassword = string.Empty;
                }
                else if (!res.IsUnauthorized && !res.IsForbidden)
                {
                    await _dialogService.ShowErrorAsync("Error", res.ErrorMessage ?? "Failed to change password.");
                }
            }
            finally
            {
                IsBusy = false;
            }
        }
    }
}
