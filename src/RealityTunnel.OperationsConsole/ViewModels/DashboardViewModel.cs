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
        private int activeSubscribers;

        [ObservableProperty]
        private int onlineUsers;

        [ObservableProperty]
        private decimal monthlyRevenueEst;

        [ObservableProperty]
        private int totalDevices;

        [ObservableProperty]
        private int activeSubscriptions;

        [ObservableProperty]
        private int expiredSubscriptions;

        [ObservableProperty]
        private string bandwidthTodayFormatted = "0 B";

        [ObservableProperty]
        private string bandwidthMonthFormatted = "0 B";

        [ObservableProperty]
        private int provisionQueuePending = 0;

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
                    ActiveSubscribers = result.Data.ActiveSubscribers;
                    OnlineUsers = result.Data.OnlineUsers;
                    MonthlyRevenueEst = result.Data.MonthlyRevenueEst;
                    TotalDevices = result.Data.TotalDevices;
                    ActiveSubscriptions = result.Data.ActiveSubscriptions;
                    ExpiredSubscriptions = result.Data.ExpiredSubscriptions;
                    BandwidthTodayFormatted = FormatBytes(result.Data.BandwidthTodayBytes);
                    BandwidthMonthFormatted = FormatBytes(result.Data.BandwidthMonthBytes);
                    LastUpdatedFormatted = DateTime.Now.ToString("HH:mm:ss");
                }
                else if (!result.IsUnauthorized && !result.IsForbidden)
                {
                    await _dialogService.ShowErrorAsync("Dashboard Error", result.ErrorMessage ?? "Failed to load dashboard metrics.");
                }

                // Load Provision Queue count
                var qRes = await _apiService.GetAsync<AdminRetryQueueDTO>(ApiRoutes.Admin.RetryQueue);
                if (qRes.IsSuccess && qRes.Data != null)
                {
                    ProvisionQueuePending = qRes.Data.Total;
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
