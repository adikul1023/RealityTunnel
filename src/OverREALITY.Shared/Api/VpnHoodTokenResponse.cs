using System.Text.Json.Serialization;

namespace OverREALITY.Shared.Api;

public class VpnHoodTokenResponse
{
    [JsonPropertyName("access_key")]
    public string AccessKey { get; set; } = string.Empty;
}
