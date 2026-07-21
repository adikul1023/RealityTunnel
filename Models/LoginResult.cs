using System;
using System.Text.Json.Serialization;

namespace RealityTunnel.Models;

public enum LoginStatus
{
    Success,
    DeviceLimitExceeded,
    DeviceOwnershipError,
    DeviceDeactivated,
    AccountDisabled,
    InvalidMasterToken,
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
    
    // For MaintenanceMode
    public int? RetryAfterSeconds { get; set; }
    
    public string? ErrorMessage { get; set; }
    public string? ErrorCode { get; set; }
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


public class ApiErrorResponse
{
    [JsonPropertyName("code")]
    public string? Code { get; set; }

    [JsonPropertyName("detail")]
    public string? Detail { get; set; }

    [JsonPropertyName("requires_2fa")]
    public bool? Requires2Fa { get; set; }
    
    [JsonPropertyName("current_devices")]
    public int? CurrentDevices { get; set; }
    
    [JsonPropertyName("max_devices")]
    public int? MaxDevices { get; set; }
    
    [JsonPropertyName("manage_devices_url")]
    public string? ManageDevicesUrl { get; set; }
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
