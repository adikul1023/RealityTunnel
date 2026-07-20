using System.Threading.Tasks;
using RealityTunnel.Models;

namespace RealityTunnel.Services;

public class InProcessVpnBackend : IVpnBackend
{
    private readonly XrayController _xrayController;

    public InProcessVpnBackend(XrayController xrayController)
    {
        _xrayController = xrayController;
    }

    public Task ConnectAsync(VpnProfile profile) => Task.Run(() => _xrayController.Start(profile));

    public Task DisconnectAsync()
    {
        _xrayController.Stop();
        return Task.CompletedTask;
    }

    public Task<bool> IsRunningAsync() => Task.FromResult(_xrayController.IsRunning());
}
