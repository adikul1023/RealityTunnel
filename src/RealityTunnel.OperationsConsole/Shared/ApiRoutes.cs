namespace RealityTunnel.OperationsConsole.Shared
{
    /// <summary>
    /// Centralized registry of all administrative and operational backend API endpoints.
    /// All API requests must use these strongly-typed route definitions to prevent hardcoding across ViewModels and Services.
    /// </summary>
    public static class ApiRoutes
    {
        public static class Admin
        {
            public const string Login = "/api/admin/login";
            public const string Me = "/api/admin/me";
            public const string Dashboard = "/api/admin/dashboard";
            public const string Accounts = "/api/admin/accounts";
            public const string Subscriptions = "/api/admin/subscriptions";
            public const string Payments = "/api/admin/payments";
            public const string Provisioning = "/api/admin/provisioning";
            public const string RetryQueue = "/api/admin/retry-queue";
            public const string SystemHealth = "/api/admin/system-health";
            public const string DeepDiagnosticsHealth = "/admin/health";

            public static string GetAccount(string accountId) => $"/api/admin/accounts/{accountId}";
            public static string SuspendAccount(string accountId) => $"/api/admin/accounts/{accountId}/suspend";
            public static string ActivateAccount(string accountId) => $"/api/admin/accounts/{accountId}/activate";
            public static string ExtendSubscription(string accountId) => $"/api/admin/accounts/{accountId}/extend-subscription";
            public static string GetDevices(string accountId) => $"/api/admin/accounts/{accountId}/devices";
            public static string LogoutAllSessions(string accountId) => $"/api/admin/accounts/{accountId}/logout-all";
            public static string GetSignals(string accountId) => $"/api/admin/accounts/{accountId}/signals";

            public static string GetSubscription(string subscriptionId) => $"/api/admin/subscription/{subscriptionId}";
            public static string ActivateSubscription(string subscriptionId) => $"/api/admin/subscription/{subscriptionId}/activate";
            public static string GraceSubscription(string subscriptionId) => $"/api/admin/subscription/{subscriptionId}/grace";
            public static string ExpireSubscription(string subscriptionId) => $"/api/admin/subscription/{subscriptionId}/expire";
            public static string CancelSubscription(string subscriptionId) => $"/api/admin/subscription/{subscriptionId}/cancel";
            public static string RenewSubscription(string subscriptionId) => $"/api/admin/subscription/{subscriptionId}/renew";

            public static string GetPayment(string paymentId) => $"/api/admin/payment/{paymentId}";
            public static string ReconcilePayment(string paymentId) => $"/api/admin/payment/{paymentId}/reconcile";
            public static string ResolvePayment(string paymentId) => $"/api/admin/payment/{paymentId}/resolve";

            public static string SyncProvisioning(string profileId) => $"/api/admin/provisioning/{profileId}/sync";
            public static string RetryProvisioning(string profileId) => $"/api/admin/provisioning/{profileId}/retry";
            public static string SuspendProvisioning(string profileId) => $"/api/admin/provisioning/{profileId}/suspend";
            public static string RestoreProvisioning(string profileId) => $"/api/admin/provisioning/{profileId}/restore";
            public static string TerminateProvisioning(string profileId) => $"/api/admin/provisioning/{profileId}/terminate";

            public static string RetryQueueItemNow(string retryId) => $"/api/admin/retry/{retryId}/retry-now";
            public static string DiscardRetryQueueItem(string retryId) => $"/api/admin/retry/{retryId}/discard";

            // Phase 2 Missing Endpoints (documented in MissingEndpoints.md)
            public const string LogsQuery = "/api/admin/logs";
            public const string RestartService = "/api/admin/infrastructure/restart-service";
            public const string ReloadXray = "/api/admin/infrastructure/reload-xray";
            public static string DeleteDevice(string accountId, string deviceGuid) => $"/api/admin/accounts/{accountId}/devices/{deviceGuid}";
        }

        public static class Recovery
        {
            public const string CreateBackup = "/api/admin/recovery/backups";
            public const string ListBackups = "/api/admin/recovery/backups";
            public static string PreviewBackup(string backupId) => $"/api/admin/recovery/backups/{backupId}/preview";
            public static string VerifyBackup(string backupId) => $"/api/admin/recovery/backups/{backupId}/verify";
            public const string PruneBackups = "/api/admin/recovery/prune";
        }

        public static class Probes
        {
            public const string Livez = "/livez";
            public const string Health = "/health";
            public const string Readyz = "/readyz";
        }
    }
}
