using System.Threading;
using System.Threading.Tasks;

namespace OverREALITY.Shared.Interfaces;

public interface ITokenProvider
{
    Task<string?> GetValidTokenAsync(CancellationToken cancellationToken = default);
    void InvalidateToken();
}
