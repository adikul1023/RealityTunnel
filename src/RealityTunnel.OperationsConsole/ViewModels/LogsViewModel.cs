using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using RealityTunnel.OperationsConsole.Services;

namespace RealityTunnel.OperationsConsole.ViewModels
{
    public partial class LogsViewModel : ObservableObject
    {
        private readonly IDialogService _dialogService;

        [ObservableProperty]
        private string searchText = string.Empty;

        [ObservableProperty]
        private string selectedSeverity = "ALL";

        [ObservableProperty]
        private int currentPage = 1;

        [ObservableProperty]
        private bool canQueryLogs = false; // Disabled per MissingEndpoints.md

        [ObservableProperty]
        private string disabledTooltip = "Backend support required (GET /api/admin/logs)";

        public LogsViewModel(IDialogService dialogService)
        {
            _dialogService = dialogService;
        }

        [RelayCommand]
        private void SearchLogs()
        {
            _ = _dialogService.ShowInfoAsync("Backend Support Required",
                "System & action log querying (GET /api/admin/logs) is documented as a missing endpoint in Phase 1 and will be supported in Phase 2.");
        }
    }
}
