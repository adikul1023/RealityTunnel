namespace RealityTunnel.Models;

public class ClientUpdate
{
    public string LatestVersion { get; set; } = "";
    public string MinimumSupportedVersion { get; set; } = "";
    public bool Mandatory { get; set; }
    public string DownloadUrl { get; set; } = "";
    public string Sha256 { get; set; } = "";
    public string ReleaseNotes { get; set; } = "";
}
