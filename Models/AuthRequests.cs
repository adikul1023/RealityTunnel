using System.Text.Json.Serialization;

namespace RealityTunnel.Models;

public class LoginRequest
{
    [JsonPropertyName("account_id")]
    public string AccountId { get; set; } = "";

    [JsonPropertyName("master_token")]
    public string MasterToken { get; set; } = "";

    [JsonPropertyName("device_guid")]
    public string DeviceGuid { get; set; } = "";
}

public class RefreshRequest
{
    [JsonPropertyName("refresh_token")]
    public string RefreshToken { get; set; } = "";
}
