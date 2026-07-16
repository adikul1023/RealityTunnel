using System;
using System.Threading.Tasks;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using RealityTunnel.OperationsConsole.Services;
using RealityTunnel.OperationsConsole.Shared;

namespace RealityTunnel.OperationsConsole.ViewModels
{
    public partial class DashboardViewModel : ObservableObject
    {
        private readonly IAdminApiService _apiService;
        private readonly IDialogService _dialogService;

        [ObservableProperty]
        private bool isBusy;

        [ObservableProperty]
        private int totalAccounts;

        [ObservableProperty]
        private int activeSubscriptions;

        [ObservableProperty]
        private int graceSubscriptions;

        [ObservableProperty]
        private int expiredSubscriptions;

        [ObservableProperty]
        private int todayPayments;

        [ObservableProperty]
        private string todayRevenueFormatted = "$0.00";

        [ObservableProperty]
        private int provisioningFailures;

        [ObservableProperty]
        private int retryQueueSize;

        [ObservableProperty]
        private int activeAdmins;

        [ObservableProperty]
        private string lastUpdatedFormatted = "Never";

        public DashboardViewModel(IAdminApiService apiService, IDialogService dialogService)
        {
            _apiService = apiService;
            _dialogService = dialogService;
        }

        [RelayCommand]
        public async Task LoadDashboardAsync()
        {
            if (IsBusy) return;
            IsBusy = true;
            try
            {
                var result = await _apiService.GetAsync<AdminDashboardDTO>(ApiRoutes.Admin.Dashboard);
                if (result.IsSuccess && result.Data != null)
                {
                    TotalAccounts = result.Data.TotalAccounts;
                    ActiveSubscriptions = result.Data.ActiveSubscriptions;
                    GraceSubscriptions = result.Data.GraceSubscriptions;
                    ExpiredSubscriptions = result.Data.ExpiredSubscriptions;
                    TodayPayments = result.Data.TodayPayments;
                    TodayRevenueFormatted = $"{(result.Data.TodayRevenueMinorUnits / 100m):C2}";
                    ProvisioningFailures = result.Data.ProvisioningFailures;
                    RetryQueueSize = result.Data.RetryQueueSize;
                    ActiveAdmins = result.Data.ActiveAdmins;
                    LastUpdatedFormatted = DateTime.Now.ToString("HH:mm:ss");
                }
                else if (!result.IsUnauthorized && !result.IsForbidden)
                {
                    await _dialogService.ShowErrorAsync("Dashboard Error", result.ErrorMessage ?? "Failed to load dashboard metrics.");
                }

                // Load Provision Queue count is now in DashboardDTO, but keeping retry queue API call just in case
                var qRes = await _apiService.GetAsync<AdminRetryQueueDTO>(ApiRoutes.Admin.RetryQueue);
                if (qRes.IsSuccess && qRes.Data != null)
                {
                    RetryQueueSize = qRes.Data.Total;
                }
            }
            finally
            {
                IsBusy = false;
            }
        }

        private static string FormatBytes(long bytes)
        {
            if (bytes <= 0) return "0 B";
            string[] units = { "B", "KB", "MB", "GB", "TB" };
            double val = bytes;
            int order = 0;
            while (val >= 1024 && order < units.Length - 1)
            {
                order++;
                val /= 1024;
            }
            return $"{val:0.##} {units[order]}";
        }
    }
}
