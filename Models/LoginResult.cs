using System;
using System.Text.Json.Serialization;

namespace RealityTunnel.Models;

public enum LoginStatus
{
    Success,
    DeviceLimitExceeded,
    ReplayDetected,
    Requires2FA,
    SubscriptionExpired,
    MandatoryUpdate,
    MaintenanceMode,
    OfflineGraceExpired,
    Error
}

public class ExchangeResult
{
    public bool Success { get; set; }
    public JwtTokens? Tokens { get; set; }
    public bool IsInitialProvisioning { get; set; }
    public string? ErrorMessage { get; set; }
}

public class LoginResult
{
    public LoginStatus Status { get; set; }
    public JwtTokens? Tokens { get; set; }
    
    // For DeviceLimitExceeded
    public DeviceLimitDetails? DeviceLimitDetails { get; set; }
    
    // For Requires2FA
    public string? TemporaryLoginToken { get; set; }
    
    // For MaintenanceMode
    public int? RetryAfterSeconds { get; set; }
    
    public string? ErrorMessage { get; set; }
}

public class DeviceLimitDetails
{
    [JsonPropertyName("current_devices")]
    public int CurrentDevices { get; set; }
    
    [JsonPropertyName("max_devices")]
    public int MaxDevices { get; set; }
    
    [JsonPropertyName("manage_devices_url")]
    public string ManageDevicesUrl { get; set; } = "";
}

public class Verify2FaRequest
{
    [JsonPropertyName("temporary_login_token")]
    public string TemporaryLoginToken { get; set; } = "";
    
    [JsonPropertyName("totp_code")]
    public string TotpCode { get; set; } = "";
}

public class ApiErrorResponse
{
    [JsonPropertyName("error")]
    public string Error { get; set; } = "";
    
    // Only populated when error is "device_limit_exceeded"
    [JsonPropertyName("current_devices")]
    public int? CurrentDevices { get; set; }
    
    [JsonPropertyName("max_devices")]
    public int? MaxDevices { get; set; }
    
    [JsonPropertyName("manage_devices_url")]
    public string? ManageDevicesUrl { get; set; }
    
    // Only populated when error is "requires_2fa"
    [JsonPropertyName("temporary_login_token")]
    public string? TemporaryLoginToken { get; set; }
}

public class ExchangeRequestDto
{
    [JsonPropertyName("exchange_token")]
    public string ExchangeToken { get; set; } = "";
    
    [JsonPropertyName("device_guid")]
    public string DeviceGuid { get; set; } = "";
}

public class ExchangeResponseDto
{
    [JsonPropertyName("access_token")]
    public string AccessToken { get; set; } = "";
    
    [JsonPropertyName("refresh_token")]
    public string RefreshToken { get; set; } = "";
    
    [JsonPropertyName("expires_in")]
    public int ExpiresIn { get; set; }
    
    [JsonPropertyName("is_initial_provisioning")]
    public bool IsInitialProvisioning { get; set; }
}
