using System.Text.Json.Serialization;

namespace OverREALITY.Shared.Api.Authentication;

public class RefreshRequest
{
    [JsonPropertyName("refresh_token")]
    public string RefreshToken { get; set; } = string.Empty;
}
