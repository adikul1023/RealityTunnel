using System.Threading;
using System.Threading.Tasks;
using OverREALITY.Shared.Errors;
using OverREALITY.Shared.Api.Authentication;

namespace OverREALITY.Shared.Interfaces;

public interface IAuthService
{
    Task<Result<LoginResponse, AuthenticationError>> LoginAsync(string accountId, string masterToken, string? twoFaCode = null, CancellationToken cancellationToken = default);
    Task<Result<bool, AuthenticationError>> LogoutAsync(CancellationToken cancellationToken = default);
    Task<Result<string, AuthenticationError>> GetValidAccessTokenAsync(CancellationToken cancellationToken = default);
    Task<bool> TryRestoreSessionAsync(CancellationToken cancellationToken = default);
}
