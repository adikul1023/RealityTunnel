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
        private ObservableCollection<AdminBackupResponseDTO> backups = new();

        [ObservableProperty]
        private bool isSuperAdmin;

        [ObservableProperty]
        private bool canRestartServices = true;

        [ObservableProperty]
        private string restartButtonsTooltip = "Restart this infrastructure service gracefully";

        [ObservableProperty]
        private string reloadXrayTooltip = "Hot-reload Xray core without dropping connections";

        [ObservableProperty]
        private bool canExecuteAdvancedRecovery = true;

        [ObservableProperty]
        private string advancedRecoveryTooltip = "Execute disaster recovery operation";

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

                if (healthRes.IsSuccess && healthRes.Data != null && healthRes.Data.Components != null)
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
                    var pg = healthRes.Data.Components.GetValueOrDefault("postgresql");
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
                    var redis = healthRes.Data.Components.GetValueOrDefault("redis");
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
                    var marzban = healthRes.Data.Components.GetValueOrDefault("marzban");
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
                    var xray = healthRes.Data.Components.GetValueOrDefault("xray");
                    ServicesList.Add(new ServiceHealthDisplayModel
                    {
                        ComponentName = "Xray Core Reality Engine",
                        ComponentKey = "xray",
                        Status = xray?.Status ?? marzban?.Status ?? "ok",
                        Detail = xray?.Detail ?? "VLESS TCP REALITY engine on Edge",
                        CanRestart = false
                    });

                    // 6. Razorpay Payment Gateway
                    var rz = healthRes.Data.Components.GetValueOrDefault("payment_gateway");
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
                if (retryRes.IsSuccess && retryRes.Data != null && retryRes.Data.PendingItems != null)
                {
                    RetryQueueItems.Clear();
                    foreach (var item in retryRes.Data.PendingItems) RetryQueueItems.Add(item);
                }

                // 3. Load backups list
                var bkRes = await _apiService.GetAsync<List<AdminBackupResponseDTO>>(ApiRoutes.Recovery.ListBackups);
                if (bkRes.IsSuccess && bkRes.Data != null)
                {
                    Backups.Clear();
                    foreach (var backup in bkRes.Data) Backups.Add(backup);
                }
            }
            catch (Exception ex)
            {
                System.IO.File.WriteAllText(@"C:\Users\arun1\.gemini\antigravity-ide\brain\fd2c6752-4f1a-4ab6-8d6d-a5d946662fec\scratch\crash.txt", ex.ToString());
                await _dialogService.ShowErrorAsync("Infrastructure Error", $"Failed to load infrastructure status: {ex.Message}");
            }
            finally { IsBusy = false; }
        }

        [RelayCommand]
        private async Task RestartServiceActionAsync(string serviceName)
        {
            if (string.IsNullOrWhiteSpace(serviceName) || !IsSuperAdmin) return;
            bool confirm = await _dialogService.ShowConfirmationAsync("Confirm Restart", $"Are you sure you want to restart the '{serviceName}' service?");
            if (!confirm) return;

            IsBusy = true;
            try
            {
                var res = await _apiService.PostAsync<object>(ApiRoutes.Admin.RestartService(serviceName));
                if (res.IsSuccess)
                {
                    await _dialogService.ShowInfoAsync("Restart Initiated", $"Restart command for {serviceName} has been queued.");
                }
                else
                {
                    await _dialogService.ShowErrorAsync("Restart Failed", res.ErrorMessage ?? "Failed to queue restart command.");
                }
            }
            finally { IsBusy = false; }
        }

        [RelayCommand]
        private async Task ReloadXrayActionAsync()
        {
            if (!IsSuperAdmin) return;
            bool confirm = await _dialogService.ShowConfirmationAsync("Confirm Reload", "Are you sure you want to reload Xray core?");
            if (!confirm) return;

            IsBusy = true;
            try
            {
                var res = await _apiService.PostAsync<object>(ApiRoutes.Admin.ReloadXray);
                if (res.IsSuccess)
                {
                    await _dialogService.ShowInfoAsync("Reload Initiated", "Xray reload command has been queued.");
                }
                else
                {
                    await _dialogService.ShowErrorAsync("Reload Failed", res.ErrorMessage ?? "Failed to queue reload command.");
                }
            }
            finally { IsBusy = false; }
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
            bool confirm = await _dialogService.ShowConfirmationAsync("Confirm Snapshot", "Are you sure you want to trigger a manual backup snapshot?");
            if (!confirm) return;

            IsBusy = true;
            try
            {
                var res = await _apiService.PostAsync<object>(ApiRoutes.Recovery.CreateBackup);
                if (res.IsSuccess)
                {
                    await _dialogService.ShowInfoAsync("Backup Created", "Snapshot successfully generated and stored.");
                    await LoadHealthAndStatusAsync();
                }
                else
                {
                    await _dialogService.ShowErrorAsync("Backup Failed", res.ErrorMessage ?? "Failed to create snapshot.");
                }
            }
            finally { IsBusy = false; }
        }

        [RelayCommand]
        private async Task PruneBackupsAsync()
        {
            if (!IsSuperAdmin) return;
            bool confirm = await _dialogService.ShowConfirmationAsync("Confirm Prune", "Are you sure you want to prune expired/over-quota backup snapshots?");
            if (!confirm) return;

            IsBusy = true;
            try
            {
                var res = await _apiService.PostAsync<object>(ApiRoutes.Recovery.PruneBackups);
                if (res.IsSuccess)
                {
                    await _dialogService.ShowInfoAsync("Pruned", "Backup retention pruning complete.");
                    await LoadHealthAndStatusAsync();
                }
                else
                {
                    await _dialogService.ShowErrorAsync("Prune Failed", res.ErrorMessage ?? "Failed to prune backups.");
                }
            }
            finally { IsBusy = false; }
        }

        [RelayCommand]
        private async Task VerifyBackupAsync(AdminBackupResponseDTO? backup)
        {
            if (backup == null || !IsSuperAdmin) return;
            IsBusy = true;
            try
            {
                var res = await _apiService.PostAsync<object>(ApiRoutes.Recovery.VerifyBackup(backup.BackupId));
                if (res.IsSuccess)
                {
                    await _dialogService.ShowInfoAsync("Verification Success", $"Cryptographic and archive integrity verified for {backup.BackupId}.");
                }
                else
                {
                    await _dialogService.ShowErrorAsync("Verification Failed", res.ErrorMessage ?? "Backup verification failed.");
                }
            }
            finally { IsBusy = false; }
        }

        [RelayCommand]
        private async Task PreviewBackupAsync(AdminBackupResponseDTO? backup)
        {
            if (backup == null) return;
            IsBusy = true;
            try
            {
                var res = await _apiService.GetAsync<object>(ApiRoutes.Recovery.PreviewBackup(backup.BackupId));
                if (res.IsSuccess && res.Data != null)
                {
                    await _dialogService.ShowInfoAsync("Preview Data", System.Text.Json.JsonSerializer.Serialize(res.Data, new System.Text.Json.JsonSerializerOptions { WriteIndented = true }));
                }
                else
                {
                    await _dialogService.ShowErrorAsync("Preview Failed", res.ErrorMessage ?? "Failed to load backup preview.");
                }
            }
            finally { IsBusy = false; }
        }
    }
}
