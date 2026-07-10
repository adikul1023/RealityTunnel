namespace RealityTunnel.Models;

public class ClientMeResponse
{
    public string AccountId { get; set; } = "";
    public string Status { get; set; } = "";
    public string? SubscriptionExpiresAt { get; set; }
    public int DeviceCount { get; set; }
    public string Plan { get; set; } = "";
    public string? Email { get; set; }
    public bool TwoFactorEnabled { get; set; }
}
