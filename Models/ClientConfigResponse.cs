using System.Text.Json.Serialization;

namespace RealityTunnel.Models;

public class ClientConfigResponse
{
    [JsonPropertyName("vpn_profile")]
    public VpnProfile VpnProfile { get; set; } = new();

    [JsonPropertyName("license_blob")]
    public LicenseBlobDto LicenseBlob { get; set; } = new();
}

public class LicenseBlobDto
{
    [JsonPropertyName("payload")]
    public string Payload { get; set; } = "";

    [JsonPropertyName("signature")]
    public string Signature { get; set; } = "";
}
