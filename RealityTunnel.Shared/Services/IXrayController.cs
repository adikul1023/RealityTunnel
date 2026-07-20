using RealityTunnel.Models;

namespace RealityTunnel.Services;

public interface IXrayController
{
    void Start(VpnProfile profile);
    void Stop();
    bool IsRunning();
}
