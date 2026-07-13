using System.Text.Json.Serialization;

namespace RealityTunnel.Models;

public class VpnProfile
{
    [JsonPropertyName("uuid")]
    public string Uuid { get; set; } = "";
    [JsonPropertyName("server_host")]
    public string ServerHost { get; set; } = "";
    [JsonPropertyName("server_port")]
    public int ServerPort { get; set; }
    [JsonPropertyName("public_key")]
    public string PublicKey { get; set; } = "";
    [JsonPropertyName("short_id")]
    public string ShortId { get; set; } = "";
    [JsonPropertyName("sni")]
    public string Sni { get; set; } = "";
    [JsonPropertyName("preferred_dns")]
    public string? PreferredDns { get; set; }
}

