using System.Threading.Tasks;
using RealityTunnel.Models;

namespace RealityTunnel.Services;

/// <summary>
/// Phase 1 implementation of <see cref="IVpnBackend"/>: a thin wrapper around the existing
/// in-process <see cref="XrayController"/>. Behaviorally identical to how
/// <see cref="VpnSessionManager"/> used <see cref="XrayController"/> directly before this
/// refactor — this class introduces the seam without changing what runs or how it runs.
///
/// This still requires the whole process to be elevated, exactly as today. It exists so that
/// a future <c>NamedPipeVpnBackend</c> (talking to the privileged helper service) can be
/// swapped in behind the same interface, per docs/PRIVILEGE_BOUNDARY_DESIGN.md.
/// </summary>
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
