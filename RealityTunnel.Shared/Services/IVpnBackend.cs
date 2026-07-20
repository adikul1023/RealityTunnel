using System.Threading.Tasks;
using RealityTunnel.Models;

namespace RealityTunnel.Services;

/// <summary>
/// The seam between session orchestration (<see cref="VpnSessionManager"/>) and whatever
/// actually performs the privileged VPN operations (starting/stopping sing-box, routes, DNS).
/// </summary>
public interface IVpnBackend
{
    Task ConnectAsync(VpnProfile profile);

    Task DisconnectAsync();

    Task<bool> IsRunningAsync();
}
