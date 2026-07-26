using System.Text.Json.Serialization;

namespace OverREALITY.Shared.Api.Authentication;

public class LoginRequest
{
    [JsonPropertyName("account_id")]
    public string AccountId { get; set; } = string.Empty;

    [JsonPropertyName("master_token")]
    public string MasterToken { get; set; } = string.Empty;

    [JsonPropertyName("device_guid")]
    public string DeviceGuid { get; set; } = string.Empty;

    [JsonPropertyName("client_type")]
    public string ClientType { get; set; } = "desktop";
}

