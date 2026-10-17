using System.Threading;
using System.Threading.Tasks;

namespace OverREALITY.Shared.Interfaces;

public interface IConnectionService
{
    Task ConnectAsync(int serverIndex = 0, CancellationToken cancellationToken = default);
    Task DisconnectAsync(CancellationToken cancellationToken = default);
}
