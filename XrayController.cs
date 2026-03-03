// Thin wrapper — all logic lives in OverREALITY.Core.VpnController.
using OverREALITY.Core;

namespace RealityTunnel;

public class XrayController
{
    private readonly VpnController _inner = new();

    public void Start(string serverIp) => _inner.Start(serverIp);
    public void Stop()                 => _inner.Stop();
    public bool IsRunning()            => _inner.IsRunning();
}
