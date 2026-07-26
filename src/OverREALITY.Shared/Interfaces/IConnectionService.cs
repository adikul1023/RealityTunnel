using System.Threading;
using System.Threading.Tasks;

namespace OverREALITY.Shared.Interfaces;

public interface IConnectionService
{
    Task ConnectAsync(CancellationToken cancellationToken = default);
    Task DisconnectAsync(CancellationToken cancellationToken = default);
}
