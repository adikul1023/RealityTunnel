using System.Threading.Tasks;
using OverREALITY.Shared.Errors;
using System.Threading;
using OverREALITY.Shared.Api.Configuration;

namespace OverREALITY.Shared.Interfaces;

public interface IConnectionProvisioningService
{
    Task<Result<VPNConfig, ProvisioningError>> ConnectProvisionAsync(CancellationToken cancellationToken = default);
}
