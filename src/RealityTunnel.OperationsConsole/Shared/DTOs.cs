using System;
using System.Collections.Generic;
using System.Text.Json.Serialization;
using CommunityToolkit.Mvvm.ComponentModel;

namespace RealityTunnel.OperationsConsole.Shared
{
    public class DeviceRemovalResponseDTO
    {
        [JsonPropertyName("success")]
        public bool Success { get; set; }

        [JsonPropertyName("active_devices_remaining")]
        public int ActiveDevicesRemaining { get; set; }
    }

    public class AdminLoginRequest
    {
        [JsonPropertyName("username")]
        public string Username { get; set; } = string.Empty;

        [JsonPropertyName("password")]
        public string Password { get; set; } = string.Empty;
    }

    public class AdminLoginResponse
    {
        [JsonPropertyName("access_token")]
        public string AccessToken { get; set; } = string.Empty;

        [JsonPropertyName("token_type")]
        public string TokenType { get; set; } = "Bearer";

        [JsonPropertyName("expires_in")]
        public int ExpiresIn { get; set; }

        [JsonPropertyName("username")]
        public string Username { get; set; } = string.Empty;

        [JsonPropertyName("role")]
        public string Role { get; set; } = string.Empty;
    }

    public class AdminProfileResponse
    {
        [JsonPropertyName("id")]
        public string Id { get; set; } = string.Empty;

        [JsonPropertyName("username")]
        public string Username { get; set; } = string.Empty;

        [JsonPropertyName("is_active")]
        public bool IsActive { get; set; }

        [JsonPropertyName("is_super_admin")]
        public bool IsSuperAdmin { get; set; }

        [JsonPropertyName("mfa_enabled")]
        public bool MfaEnabled { get; set; }
    }

    public class AdminAccountResponse
    {
        [JsonPropertyName("id")]
        public string Id { get; set; } = string.Empty;

        [JsonPropertyName("account_id")]
        public string AccountId { get; set; } = string.Empty;

        [JsonPropertyName("status")]
        public string Status { get; set; } = string.Empty;

        [JsonPropertyName("plan_id")]
        public string PlanId { get; set; } = string.Empty;

        [JsonPropertyName("subscription_expires_at")]
        public DateTime? SubscriptionExpiresAt { get; set; }

        [JsonPropertyName("created_at")]
        public DateTime? CreatedAt { get; set; }
    }

    public class AdminAccountListResponse
    {
        [JsonPropertyName("accounts")]
        public List<AdminAccountResponse> Accounts { get; set; } = new();

        [JsonPropertyName("total")]
        public int Total { get; set; }
    }

    public class AdminDeviceResponse
    {
        [JsonPropertyName("device_guid")]
        public string DeviceGuid { get; set; } = string.Empty;

        [JsonPropertyName("friendly_name")]
        public string? FriendlyName { get; set; }

        [JsonPropertyName("is_active")]
        public bool IsActive { get; set; }

        [JsonPropertyName("first_seen_at")]
        public DateTime? FirstSeenAt { get; set; }

        [JsonPropertyName("last_seen_at")]
        public DateTime? LastSeenAt { get; set; }
    }

    public class AdminDeviceListResponse
    {
        [JsonPropertyName("devices")]
        public List<AdminDeviceResponse> Devices { get; set; } = new();
    }

    public class AdminLogoutAllResponse
    {
        [JsonPropertyName("revoked_count")]
        public int RevokedCount { get; set; }
    }

    public class AdminSignalResponse
    {
        [JsonPropertyName("id")]
        public string Id { get; set; } = string.Empty;

        [JsonPropertyName("event_type")]
        public string EventType { get; set; } = string.Empty;

        [JsonPropertyName("source_ip")]
        public string? SourceIp { get; set; }

        [JsonPropertyName("user_agent")]
        public string? UserAgent { get; set; }

        [JsonPropertyName("occurred_at")]
        public DateTime? OccurredAt { get; set; }

        [JsonPropertyName("success")]
        public bool Success { get; set; }
    }

    public class AdminSignalListResponse
    {
        [JsonPropertyName("signals")]
        public List<AdminSignalResponse> Signals { get; set; } = new();

        [JsonPropertyName("total")]
        public int Total { get; set; }
    }

    public class AdminDashboardDTO
    {
        [JsonPropertyName("total_accounts")]
        public int TotalAccounts { get; set; }

        [JsonPropertyName("active_subscriptions")]
        public int ActiveSubscriptions { get; set; }

        [JsonPropertyName("grace_subscriptions")]
        public int GraceSubscriptions { get; set; }

        [JsonPropertyName("expired_subscriptions")]
        public int ExpiredSubscriptions { get; set; }

        [JsonPropertyName("today_payments")]
        public int TodayPayments { get; set; }

        [JsonPropertyName("today_revenue_minor_units")]
        public int TodayRevenueMinorUnits { get; set; }

        [JsonPropertyName("provisioning_failures")]
        public int ProvisioningFailures { get; set; }

        [JsonPropertyName("retry_queue_size")]
        public int RetryQueueSize { get; set; }

        [JsonPropertyName("active_admins")]
        public int ActiveAdmins { get; set; }
    }

    public partial class AdminSubscriptionDTO : ObservableObject
    {
        [JsonPropertyName("id")]
        public string Id { get; set; } = string.Empty;

        [JsonPropertyName("account_id")]
        public string AccountId { get; set; } = string.Empty;

        [JsonPropertyName("plan")]
        public string Plan { get; set; } = string.Empty;

        [JsonPropertyName("status")]
        public string Status { get; set; } = string.Empty;

        [JsonPropertyName("data_used_bytes")]
        public long DataUsedBytes { get; set; }

        [JsonPropertyName("data_limit_bytes")]
        public long DataLimitBytes { get; set; }

        [JsonPropertyName("expires_at")]
        public DateTime? ExpiresAt { get; set; }

        [ObservableProperty]
        [JsonIgnore]
        private string? selectedPlanId;
        
        [ObservableProperty]
        [JsonIgnore]
        private bool isPlanChanged;

        partial void OnSelectedPlanIdChanged(string? value)
        {
            IsPlanChanged = value != null && !value.Equals(Plan, StringComparison.OrdinalIgnoreCase);
        }
    }

    public class AdminSubscriptionRevokeRequest
    {
        [JsonPropertyName("reason")]
        public string Reason { get; set; } = string.Empty;
    }

    public class AdminPlanDTO
    {
        [JsonPropertyName("id")]
        public string Id { get; set; } = string.Empty;

        [JsonPropertyName("name")]
        public string Name { get; set; } = string.Empty;

        [JsonPropertyName("data_limit_bytes")]
        public long DataLimitBytes { get; set; }

        [JsonPropertyName("duration_days")]
        public int DurationDays { get; set; }

        [JsonPropertyName("price_minor_units")]
        public int PriceMinorUnits { get; set; }
    }

    public class AdminSubscriptionPlanRequest
    {
        [JsonPropertyName("new_plan_id")]
        public string PlanId { get; set; } = string.Empty;
    }

    public class AdminSubscriptionListDTO
    {
        [JsonPropertyName("subscriptions")]
        public List<AdminSubscriptionDTO> Subscriptions { get; set; } = new();

        [JsonPropertyName("total")]
        public int Total { get; set; }
    }

    public class AdminPaymentDTO
    {
        [JsonPropertyName("id")]
        public string Id { get; set; } = string.Empty;

        [JsonPropertyName("account_id")]
        public string AccountId { get; set; } = string.Empty;

        [JsonPropertyName("plan")]
        public string Plan { get; set; } = string.Empty;

        [JsonPropertyName("amount")]
        public decimal Amount { get; set; }

        [JsonPropertyName("status")]
        public string Status { get; set; } = string.Empty;

        [JsonPropertyName("created_at")]
        public DateTime? CreatedAt { get; set; }
    }

    public class AdminPaymentListDTO
    {
        [JsonPropertyName("payments")]
        public List<AdminPaymentDTO> Payments { get; set; } = new();

        [JsonPropertyName("total")]
        public int Total { get; set; }
    }

    public class AdminProvisioningDTO
    {
        [JsonPropertyName("id")]
        public string Id { get; set; } = string.Empty;

        [JsonPropertyName("account_id")]
        public string AccountId { get; set; } = string.Empty;

        [JsonPropertyName("vpn_profile_uuid")]
        public string VpnProfileUuid { get; set; } = string.Empty;

        [JsonPropertyName("marzban_username")]
        public string MarzbanUsername { get; set; } = string.Empty;

        [JsonPropertyName("inbound")]
        public string Inbound { get; set; } = "VLESS TCP REALITY";

        [JsonPropertyName("current_flow")]
        public string CurrentFlow { get; set; } = string.Empty;

        [JsonPropertyName("reality_public_key")]
        public string RealityPublicKey { get; set; } = string.Empty;

        [JsonPropertyName("sni")]
        public string Sni { get; set; } = string.Empty;

        [JsonPropertyName("last_provision_time")]
        public DateTime? LastProvisionTime { get; set; }

        [JsonPropertyName("provision_status")]
        public string ProvisionStatus { get; set; } = string.Empty;
    }

    public class AdminProvisioningListDTO
    {
        [JsonPropertyName("profiles")]
        public List<AdminProvisioningDTO> Profiles { get; set; } = new();

        [JsonPropertyName("total")]
        public int Total { get; set; }
    }

    public class ComponentStatusDTO
    {
        [JsonPropertyName("status")]
        public string Status { get; set; } = "ok";

        [JsonPropertyName("latency_ms")]
        public double? LatencyMs { get; set; }

        [JsonPropertyName("detail")]
        public string? Detail { get; set; }
    }

    public class AdminHealthResponseDTO
    {
        [JsonPropertyName("status")]
        public string Status { get; set; } = "ok";

        [JsonPropertyName("version")]
        public string? Version { get; set; }

        [JsonPropertyName("components")]
        public Dictionary<string, ComponentStatusDTO>? Components { get; set; }
    }

    public class AdminSystemHealthDTO : AdminHealthResponseDTO
    {
        [JsonPropertyName("postgres")]
        public ComponentStatusDTO Postgres
        {
            get => Components != null && Components.TryGetValue("postgres", out var c) ? c : new ComponentStatusDTO { Status = "ok" };
            set { if (Components == null) Components = new(); Components["postgres"] = value; }
        }

        [JsonPropertyName("marzban")]
        public ComponentStatusDTO Marzban
        {
            get => Components != null && Components.TryGetValue("marzban", out var c) ? c : new ComponentStatusDTO { Status = "ok" };
            set { if (Components == null) Components = new(); Components["marzban"] = value; }
        }

        [JsonPropertyName("razorpay")]
        public ComponentStatusDTO Razorpay
        {
            get => Components != null && Components.TryGetValue("razorpay", out var c) ? c : new ComponentStatusDTO { Status = "ok" };
            set { if (Components == null) Components = new(); Components["razorpay"] = value; }
        }

        [JsonPropertyName("redis")]
        public ComponentStatusDTO Redis
        {
            get => Components != null && Components.TryGetValue("redis", out var c) ? c : new ComponentStatusDTO { Status = "ok" };
            set { if (Components == null) Components = new(); Components["redis"] = value; }
        }
    }

    public class AdminRetryItemDTO
    {
        [JsonPropertyName("id")]
        public string Id { get; set; } = string.Empty;

        [JsonPropertyName("operation_type")]
        public string OperationType { get; set; } = string.Empty;

        [JsonPropertyName("attempt_count")]
        public int AttemptCount { get; set; }

        [JsonPropertyName("next_retry_at")]
        public DateTime? NextRetryAt { get; set; }

        [JsonPropertyName("payload")]
        public string? Payload { get; set; }
    }

    public class AdminRetryQueueDTO
    {
        [JsonPropertyName("items")]
        public List<AdminRetryItemDTO> PendingItems { get; set; } = new();

        [JsonPropertyName("pending_count")]
        public int Total { get; set; }
    }

    public class AdminSubscriptionGraceRequest
    {
        [JsonPropertyName("grace_duration_days")]
        public int GraceDurationDays { get; set; } = 7;
    }

    public class AdminSubscriptionRenewRequest
    {
        [JsonPropertyName("new_expires_at")]
        public DateTime NewExpiresAt { get; set; }
    }

    public class AdminPaymentResolveRequest
    {
        [JsonPropertyName("reason")]
        public string Reason { get; set; } = string.Empty;
    }

    public class ExtendSubscriptionRequest
    {
        [JsonPropertyName("days")]
        public int Days { get; set; }
    }
    public class AdminGrantSubscriptionRequest
    {
        [JsonPropertyName("plan_id")]
        public string PlanId { get; set; } = string.Empty;

        [JsonPropertyName("duration_days")]
        public int DurationDays { get; set; }

        [JsonPropertyName("payment_method")]
        public string? PaymentMethod { get; set; }

        [JsonPropertyName("payment_reference")]
        public string? PaymentReference { get; set; }

        [JsonPropertyName("notes")]
        public string? Notes { get; set; }
    }

    public class AdminGrantSubscriptionResponse
    {
        [JsonPropertyName("success")]
        public bool Success { get; set; }

        [JsonPropertyName("plan")]
        public string Plan { get; set; } = string.Empty;

        [JsonPropertyName("expires_at")]
        public DateTime? ExpiresAt { get; set; }

        [JsonPropertyName("provisioning_state")]
        public string ProvisioningState { get; set; } = string.Empty;

        [JsonPropertyName("sync_status")]
        public string SyncStatus { get; set; } = string.Empty;
    }

    public class AdminChangePasswordResponse
    {
        [JsonPropertyName("success")]
        public bool Success { get; set; }

        [JsonPropertyName("message")]
        public string Message { get; set; } = string.Empty;
    }

    public class AdminSystemConfigUpdateResponse
    {
        [JsonPropertyName("success")]
        public bool Success { get; set; }

        [JsonPropertyName("reloaded_services")]
        public List<string> ReloadedServices { get; set; } = new();
    }

    public class AuditEventItemDTO
    {
        [JsonPropertyName("event_id")]
        public string EventId { get; set; } = string.Empty;

        [JsonPropertyName("timestamp")]
        public string Timestamp { get; set; } = string.Empty;

        [JsonPropertyName("event_type")]
        public string EventType { get; set; } = string.Empty;

        [JsonPropertyName("source")]
        public string Source { get; set; } = string.Empty;

        [JsonPropertyName("actor_id")]
        public string? ActorId { get; set; }

        [JsonPropertyName("target_id")]
        public string? TargetId { get; set; }

        [JsonPropertyName("details")]
        public Dictionary<string, object>? Details { get; set; }

        [JsonPropertyName("ip_hash")]
        public string? IpHash { get; set; }
    }

    public class AuditEventCursorPageDTO
    {
        [JsonPropertyName("items")]
        public List<AuditEventItemDTO> Items { get; set; } = new();

        [JsonPropertyName("next_cursor")]
        public string? NextCursor { get; set; }

        [JsonPropertyName("prev_cursor")]
        public string? PrevCursor { get; set; }

        [JsonPropertyName("has_more")]
        public bool HasMore { get; set; }
    }
    public class AdminBackupResponseDTO
    {
        [JsonPropertyName("backup_id")]
        public string BackupId { get; set; } = string.Empty;

        [JsonPropertyName("created_at")]
        public DateTime CreatedAt { get; set; }

        [JsonPropertyName("postgres_revision")]
        public string PostgresRevision { get; set; } = string.Empty;

        [JsonPropertyName("backup_size_bytes")]
        public long BackupSizeBytes { get; set; }
        
        [JsonPropertyName("application_version")]
        public string ApplicationVersion { get; set; } = string.Empty;
    }
}
