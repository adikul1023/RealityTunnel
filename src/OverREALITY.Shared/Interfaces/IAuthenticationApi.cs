using System.Threading;
using System.Threading.Tasks;
using OverREALITY.Shared.Api.Authentication;
using OverREALITY.Shared.Errors;

namespace OverREALITY.Shared.Interfaces;

public interface IAuthenticationApi
{
    Task<Result<LoginResponse, AuthenticationError>> LoginAsync(LoginRequest request, CancellationToken cancellationToken = default);
    Task<Result<LoginResponse, AuthenticationError>> RefreshAsync(RefreshRequest request, CancellationToken cancellationToken = default);
}
