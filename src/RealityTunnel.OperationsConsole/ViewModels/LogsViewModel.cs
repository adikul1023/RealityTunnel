using System.Collections.ObjectModel;
using System.Threading.Tasks;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using RealityTunnel.OperationsConsole.Services;
using RealityTunnel.OperationsConsole.Shared;

namespace RealityTunnel.OperationsConsole.ViewModels
{
    public partial class LogsViewModel : ObservableObject
    {
        private readonly IAdminApiService _apiService;
        private readonly IDialogService _dialogService;

        [ObservableProperty]
        private string searchText = string.Empty;

        [ObservableProperty]
        private string selectedSeverity = "ALL";

        [ObservableProperty]
        private int currentPage = 1;

        [ObservableProperty]
        private bool isBusy = false;

        [ObservableProperty]
        private ObservableCollection<AuditEventItemDTO> logs = new();

        public LogsViewModel(IAdminApiService apiService, IDialogService dialogService)
        {
            _apiService = apiService;
            _dialogService = dialogService;
        }

        [RelayCommand]
        public async Task SearchLogsAsync()
        {
            if (IsBusy) return;
            IsBusy = true;
            try
            {
                var url = $"{ApiRoutes.Admin.AuditEvents}?limit=50";
                var result = await _apiService.GetAsync<AuditEventCursorPageDTO>(url);
                if (result.IsSuccess && result.Data != null)
                {
                    Logs.Clear();
                    foreach (var item in result.Data.Items)
                    {
                        Logs.Add(item);
                    }
                }
                else
                {
                    await _dialogService.ShowErrorAsync("Error", result.ErrorMessage ?? "Failed to load audit logs.");
                }
            }
            finally
            {
                IsBusy = false;
            }
        }
    }
}
