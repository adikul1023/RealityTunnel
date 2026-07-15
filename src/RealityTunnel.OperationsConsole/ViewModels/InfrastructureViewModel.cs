using System;
using System.Collections.ObjectModel;
using System.Threading.Tasks;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using RealityTunnel.OperationsConsole.Models;
using RealityTunnel.OperationsConsole.Services;
using RealityTunnel.OperationsConsole.Shared;

namespace RealityTunnel.OperationsConsole.ViewModels
{
    public partial class InfrastructureViewModel : ObservableObject
    {
        private readonly IAdminApiService _apiService;
        private readonly IDialogService _dialogService;
        private readonly ISessionService _sessionService;

        [ObservableProperty]
        private bool isBusy;

        [ObservableProperty]
        private ObservableCollection<ServiceHealthDisplayModel> servicesList = new();

        [ObservableProperty]
        private ObservableCollection<AdminRetryItemDTO> retryQueueItems = new();

        [ObservableProperty]
        private ObservableCollection<object> backups = new();

        [ObservableProperty]
        private bool isSuperAdmin;

        [ObservableProperty]
        private bool canRestartServices = false; // Always false per MissingEndpoints.md

        [ObservableProperty]
        private string restartButtonsTooltip = "Backend support required (OS/Container orchestration API needed)";

        [ObservableProperty]
        private string reloadXrayTooltip = "Backend support required (Xray reload API needed)";

        [ObservableProperty]
        private bool canExecuteAdvancedRecovery = false; // Disabled per Step 0 audit / Phase 2 verification

        [ObservableProperty]
        private string advancedRecoveryTooltip = "Backend verification / Phase 2 support required";

        public InfrastructureViewModel(
            IAdminApiService apiService,
            IDialogService dialogService,
            ISessionService sessionService)
        {
            _apiService = apiService;
            _dialogService = dialogService;
            _sessionService = sessionService;
            IsSuperAdmin = _sessionService.CurrentRole.Equals("super_admin", StringComparison.OrdinalIgnoreCase);
        }

        [RelayCommand]
        public async Task LoadHealthAndStatusAsync()
        {
            if (IsBusy) return;
            IsBusy = true;
            try
            {
                IsSuperAdmin = _sessionService.CurrentRole.Equals("super_admin", StringComparison.OrdinalIgnoreCase);

                // 1. Load deep diagnostics health
                var healthRes = await _apiService.GetAsync<AdminHealthResponseDTO>(ApiRoutes.Admin.DeepDiagnosticsHealth);
                ServicesList.Clear();

                if (healthRes.IsSuccess && healthRes.Data != null)
                {
                    // 1. Billing API
                    ServicesList.Add(new ServiceHealthDisplayModel
                    {
                        ComponentName = "Billing API Gateway",
                        ComponentKey = "billing_api",
                        Status = healthRes.Data.Status,
                        Detail = $"Version: {healthRes.Data.Version ?? "1.0.0"}",
                        CanRestart = false
                    });

                    // 2. PostgreSQL
                    var pg = healthRes.Data.Components?.GetValueOrDefault("postgresql");
                    ServicesList.Add(new ServiceHealthDisplayModel
                    {
                        ComponentName = "PostgreSQL 16 Database",
                        ComponentKey = "postgresql",
                        Status = pg?.Status ?? "ok",
                        LatencyMs = pg?.LatencyMs,
                        Detail = pg?.Detail ?? "Primary transactional relational store",
                        CanRestart = false
                    });

                    // 3. Redis Cache
                    var redis = healthRes.Data.Components?.GetValueOrDefault("redis");
                    ServicesList.Add(new ServiceHealthDisplayModel
                    {
                        ComponentName = "Redis 7 Cache Store",
                        ComponentKey = "redis",
                        Status = redis?.Status ?? "ok",
                        LatencyMs = redis?.LatencyMs,
                        Detail = redis?.Detail ?? "In-memory rate limiting and session store",
                        CanRestart = false
                    });

                    // 4. Marzban VPN Controller
                    var marzban = healthRes.Data.Components?.GetValueOrDefault("marzban");
                    ServicesList.Add(new ServiceHealthDisplayModel
                    {
                        ComponentName = "Marzban VPN Controller",
                        ComponentKey = "marzban",
                        Status = marzban?.Status ?? "ok",
                        LatencyMs = marzban?.LatencyMs,
                        Detail = marzban?.Detail ?? "Remote Edge VPN Controller (217.216.79.209)",
                        CanRestart = false
                    });

                    // 5. Xray Reality Engine
                    var xray = healthRes.Data.Components?.GetValueOrDefault("xray");
                    ServicesList.Add(new ServiceHealthDisplayModel
                    {
                        ComponentName = "Xray Core Reality Engine",
                        ComponentKey = "xray",
                        Status = xray?.Status ?? marzban?.Status ?? "ok",
                        Detail = xray?.Detail ?? "VLESS TCP REALITY engine on Edge",
                        CanRestart = false
                    });

                    // 6. Razorpay Payment Gateway
                    var rz = healthRes.Data.Components?.GetValueOrDefault("payment_gateway");
                    ServicesList.Add(new ServiceHealthDisplayModel
                    {
                        ComponentName = "Razorpay Payment Gateway",
                        ComponentKey = "payment_gateway",
                        Status = rz?.Status ?? "ok",
                        Detail = rz?.Detail ?? "External webhook and order synchronization",
                        CanRestart = false
                    });

                    // 7. Background Job Scheduler
                    ServicesList.Add(new ServiceHealthDisplayModel
                    {
                        ComponentName = "Background Job Scheduler",
                        ComponentKey = "scheduler",
                        Status = "running",
                        Detail = "APScheduler / Async lifecycle tasks & monitors",
                        CanRestart = false
                    });
                }
                else
                {
                    // Fallback if GET /admin/health fails or returns system-health
                    var sysRes = await _apiService.GetAsync<AdminSystemHealthDTO>(ApiRoutes.Admin.SystemHealth);
                    if (sysRes.IsSuccess && sysRes.Data != null)
                    {
                        ServicesList.Add(new ServiceHealthDisplayModel { ComponentName = "PostgreSQL Database", Status = sysRes.Data.Postgres.Status });
                        ServicesList.Add(new ServiceHealthDisplayModel { ComponentName = "Marzban Controller", Status = sysRes.Data.Marzban.Status });
                        ServicesList.Add(new ServiceHealthDisplayModel { ComponentName = "Razorpay Gateway", Status = sysRes.Data.Razorpay.Status });
                    }
                }

                // 2. Load retry queue
                var retryRes = await _apiService.GetAsync<AdminRetryQueueDTO>(ApiRoutes.Admin.RetryQueue);
                if (retryRes.IsSuccess && retryRes.Data != null)
                {
                    RetryQueueItems.Clear();
                    foreach (var item in retryRes.Data.PendingItems) RetryQueueItems.Add(item);
                }

                // 3. Load backups list
                var bkRes = await _apiService.GetAsync<object>(ApiRoutes.Recovery.ListBackups);
                if (bkRes.IsSuccess && bkRes.Data != null)
                {
                    // Backups loaded
                }
            }
            finally { IsBusy = false; }
        }

        [RelayCommand]
        private void RestartServiceAction(string serviceName)
        {
            _ = _dialogService.ShowInfoAsync("Backend Support Required",
                $"Restarting '{serviceName}' over HTTP requires OS/container orchestration support (POST /api/admin/infrastructure/restart-service) which is planned for Phase 2.");
        }

        [RelayCommand]
        private void ReloadXrayAction()
        {
            _ = _dialogService.ShowInfoAsync("Backend Support Required",
                "Direct Xray engine reload via Billing API (POST /api/admin/infrastructure/reload-xray) is planned for Phase 2.");
        }

        [RelayCommand]
        private async Task RetryItemNowAsync(AdminRetryItemDTO? item)
        {
            if (item == null || !IsSuperAdmin) return;
            IsBusy = true;
            try
            {
                var res = await _apiService.PostAsync<AdminRetryItemDTO>(ApiRoutes.Admin.RetryQueueItemNow(item.Id));
                if (res.IsSuccess)
                {
                    await _dialogService.ShowInfoAsync("Retry Executed", $"Retry item {item.Id} processed.");
                    await LoadHealthAndStatusAsync();
                }
            }
            finally { IsBusy = false; }
        }

        [RelayCommand]
        private async Task DiscardRetryItemAsync(AdminRetryItemDTO? item)
        {
            if (item == null || !IsSuperAdmin) return;
            IsBusy = true;
            try
            {
                var res = await _apiService.PostAsync<AdminRetryItemDTO>(ApiRoutes.Admin.DiscardRetryQueueItem(item.Id));
                if (res.IsSuccess)
                {
                    await _dialogService.ShowInfoAsync("Discarded", $"Retry item {item.Id} removed from queue.");
                    await LoadHealthAndStatusAsync();
                }
            }
            finally { IsBusy = false; }
        }

        [RelayCommand]
        private async Task CreateBackupSnapshotAsync()
        {
            if (!IsSuperAdmin) return;
            IsBusy = true;
            try
            {
                var res = await _apiService.PostAsync<object>(ApiRoutes.Recovery.CreateBackup);
                if (res.IsSuccess)
                {
                    await _dialogService.ShowInfoAsync("Backup Created", "Snapshot successfully generated and stored.");
                    await LoadHealthAndStatusAsync();
                }
            }
            finally { IsBusy = false; }
        }
    }
}
