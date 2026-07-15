using System;
using System.Collections.Generic;
using CommunityToolkit.Mvvm.ComponentModel;
using RealityTunnel.OperationsConsole.Shared;

namespace RealityTunnel.OperationsConsole.Models
{
    public partial class UserAccountDisplayModel : ObservableObject
    {
        [ObservableProperty]
        private string id = string.Empty;

        [ObservableProperty]
        private string accountId = string.Empty;

        [ObservableProperty]
        private string status = string.Empty;

        [ObservableProperty]
        private string planId = string.Empty;

        [ObservableProperty]
        private DateTime? subscriptionExpiresAt;

        [ObservableProperty]
        private DateTime? createdAt;

        [ObservableProperty]
        private long dataUsedBytes;

        [ObservableProperty]
        private long dataLimitBytes = 53687091200; // Default 50 GB

        [ObservableProperty]
        private int deviceCount;

        [ObservableProperty]
        private List<AdminDeviceResponse> devices = new();

        [ObservableProperty]
        private AdminSubscriptionDTO? subscription;

        [ObservableProperty]
        private AdminProvisioningDTO? provisioning;

        [ObservableProperty]
        private List<AdminSignalResponse> recentSignals = new();

        public string FormattedDataUsage => $"{FormatBytes(DataUsedBytes)} / {FormatBytes(DataLimitBytes)}";

        public double UsagePercentage => DataLimitBytes > 0 ? Math.Min(100.0, Math.Round((double)DataUsedBytes / DataLimitBytes * 100.0, 1)) : 0.0;

        public string FormattedExpiry => SubscriptionExpiresAt.HasValue ? SubscriptionExpiresAt.Value.ToLocalTime().ToString("yyyy-MM-dd HH:mm") : "N/A";

        public string StatusColor => Status.ToUpperInvariant() switch
        {
            "ACTIVE" => "#10B981",    // Green
            "SUSPENDED" => "#EF4444", // Red
            "EXPIRED" => "#F59E0B",   // Amber
            _ => "#6B7280"            // Gray
        };

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

    public partial class ServiceHealthDisplayModel : ObservableObject
    {
        [ObservableProperty]
        private string componentName = string.Empty;

        [ObservableProperty]
        private string componentKey = string.Empty;

        [ObservableProperty]
        private string status = "ok";

        [ObservableProperty]
        private double? latencyMs;

        [ObservableProperty]
        private string? detail;

        [ObservableProperty]
        private bool canRestart;

        [ObservableProperty]
        private string restartTooltip = "Backend support required (Orchestration API needed)";

        public string FormattedStatus => Status.ToUpperInvariant();

        public string StatusColor => Status.ToLowerInvariant() switch
        {
            "ok" or "running" or "active" => "#10B981",
            "degraded" or "warn" => "#F59E0B",
            _ => "#EF4444"
        };
    }
}
