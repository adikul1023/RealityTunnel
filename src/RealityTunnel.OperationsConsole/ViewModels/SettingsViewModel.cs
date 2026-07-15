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
    }
}
