using System.Threading.Tasks;
using RealityTunnel.Models;

namespace RealityTunnel.Services;

/// <summary>
/// The seam between session orchestration (<see cref="VpnSessionManager"/>) and whatever
/// actually performs the privileged VPN operations (starting/stopping sing-box, routes, DNS).
///
/// Deliberately kept to exactly these members — see docs/PRIVILEGE_BOUNDARY_DESIGN.md §8.
/// Today the only implementation is <see cref="InProcessVpnBackend"/>, which wraps the
/// existing in-process <see cref="RealityTunnel.XrayController"/> with no behavior change.
/// A future <c>NamedPipeVpnBackend</c> will implement this same interface against the
/// privileged helper service instead, per the design document's migration plan.
/// </summary>
public interface IVpnBackend
{
    Task ConnectAsync(VpnProfile profile);

    Task DisconnectAsync();

    Task<bool> IsRunningAsync();
}
