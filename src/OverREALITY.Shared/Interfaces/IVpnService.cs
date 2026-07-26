using System;
using System.Threading.Tasks;
using OverREALITY.Shared.Enums;
using OverREALITY.Shared.Errors;
using OverREALITY.Shared.Api.Configuration;

namespace OverREALITY.Shared.Interfaces;

public interface IVpnService
{
    event EventHandler<ApplicationState>? StateChanged;
    event EventHandler<VpnStats>? StatsUpdated;

    Task<Result<bool, VpnError>> ConnectAsync(VPNConfig config);
    Task<Result<bool, VpnError>> DisconnectAsync();
}
