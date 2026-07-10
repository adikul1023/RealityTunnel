namespace RealityTunnel.Models;

public enum SessionState
{
    Authenticated,
    Refreshing,
    Expired,
    ReplayDetected,
    Offline
}
