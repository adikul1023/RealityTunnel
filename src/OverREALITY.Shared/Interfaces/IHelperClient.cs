using System.Threading;
using System.Threading.Tasks;
using OverREALITY.Shared.Api.VpnRuntime;
using OverREALITY.Shared.Errors;

namespace OverREALITY.Shared.Interfaces;

public interface IHelperClient
{
    Task<Result<bool, HelperError>> StartAsync(StartVpnRequest request, CancellationToken cancellationToken = default);
    Task<Result<bool, HelperError>> StopAsync(CancellationToken cancellationToken = default);
    Task<Result<HelperStatus, HelperError>> GetStatusAsync(CancellationToken cancellationToken = default);
    Task<Result<bool, HelperError>> PingAsync(CancellationToken cancellationToken = default);
}
