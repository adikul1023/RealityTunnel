using System.Text.Json.Serialization;

namespace OverREALITY.Shared.Api.Configuration;

public class ClientConfigResponse
{
    [JsonPropertyName("vpn_profile")]
    public ServerProfileDto VpnProfile { get; set; } = new();
}

public class ServerProfileDto
{
    [JsonPropertyName("server_host")]
    public string Server { get; set; } = string.Empty;

    [JsonPropertyName("server_port")]
    public int Port { get; set; }

    [JsonPropertyName("uuid")]
    public string Uuid { get; set; } = string.Empty;

    [JsonPropertyName("public_key")]
    public string PublicKey { get; set; } = string.Empty;

    [JsonPropertyName("short_id")]
    public string ShortId { get; set; } = string.Empty;

    [JsonPropertyName("sni")]
    public string Sni { get; set; } = string.Empty;

    [JsonPropertyName("preferred_dns")]
    public string? PreferredDns { get; set; }

    // Hardcode or keep defaults for properties not returned by the backend yet
    public string Transport { get; set; } = "tcp";
    public string Fingerprint { get; set; } = "chrome";
}
