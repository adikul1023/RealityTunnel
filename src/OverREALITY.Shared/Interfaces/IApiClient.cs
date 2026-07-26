using System.Threading;
using System.Threading.Tasks;
using OverREALITY.Shared.Errors;

namespace OverREALITY.Shared.Interfaces;

public interface IApiClient
{
    Task<Result<TResponse, ApiError>> GetAsync<TResponse>(string endpoint, CancellationToken cancellationToken = default);
    Task<Result<TResponse, ApiError>> PostAsync<TRequest, TResponse>(string endpoint, TRequest payload, CancellationToken cancellationToken = default);
}
