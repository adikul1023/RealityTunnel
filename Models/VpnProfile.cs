namespace RealityTunnel.Models;

public class VpnProfile
{
    public string Uuid { get; set; } = "";
    public string ServerIp { get; set; } = "";
    public string PublicKey { get; set; } = "";
    public string Sni { get; set; } = "";
    public string? Dns { get; set; }
}

