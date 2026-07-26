using System;
using System.Net;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using OverREALITY.Shared.Errors;
using OverREALITY.Shared.Interfaces;

namespace OverREALITY.Core.Services;

public class ApiClient : IApiClient
{
    private readonly HttpClient _httpClient;
    private readonly IDomainResolver _domainResolver;
    private readonly ITokenProvider _tokenProvider;
    private readonly ISecureStorage _secureStorage;
    private readonly ILogger<ApiClient> _logger;

    public ApiClient(HttpClient httpClient, IDomainResolver domainResolver, ITokenProvider tokenProvider, ISecureStorage secureStorage, ILogger<ApiClient> logger)
    {
        _httpClient = httpClient;
        _domainResolver = domainResolver;
        _tokenProvider = tokenProvider;
        _secureStorage = secureStorage;
        _logger = logger;
        
        _httpClient.BaseAddress = new Uri(_domainResolver.ApiBaseUrl);
        _httpClient.Timeout = TimeSpan.FromSeconds(30);
    }

    private async Task<HttpRequestMessage> CreateRequestAsync(HttpMethod method, string endpoint, object? payload = null)
    {
        var request = new HttpRequestMessage(method, endpoint);
        if (payload != null)
        {
            request.Content = JsonContent.Create(payload);
        }

        var token = await _tokenProvider.GetValidTokenAsync();
        if (!string.IsNullOrEmpty(token))
        {
            request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
        }

        var deviceGuid = await _secureStorage.GetSecureAsync("device_guid");
        if (!string.IsNullOrEmpty(deviceGuid))
        {
            request.Headers.Add("X-Device-Guid", deviceGuid);
            request.Headers.Add("X-Device-ID", deviceGuid);
        }

        return request;
    }

    public async Task<Result<TResponse, ApiError>> GetAsync<TResponse>(string endpoint, CancellationToken cancellationToken = default)
    {
        try
        {
            using var request = await CreateRequestAsync(HttpMethod.Get, endpoint);
            var response = await _httpClient.SendAsync(request, cancellationToken);
            return await ProcessResponse<TResponse>(response);
        }
        catch (TaskCanceledException ex)
        {
            _logger.LogError(ex, "Request timed out for endpoint {Endpoint}", endpoint);
            return Result<TResponse, ApiError>.Failure(new ApiError { Message = "Request timed out.", Code = "TIMEOUT", Retryable = true, Exception = ex });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Request failed for endpoint {Endpoint}", endpoint);
            return Result<TResponse, ApiError>.Failure(new ApiError { Message = "An unexpected error occurred.", Code = "UNKNOWN", Exception = ex });
        }
    }

    public async Task<Result<TResponse, ApiError>> PostAsync<TRequest, TResponse>(string endpoint, TRequest payload, CancellationToken cancellationToken = default)
    {
        try
        {
            using var request = await CreateRequestAsync(HttpMethod.Post, endpoint, payload);
            var response = await _httpClient.SendAsync(request, cancellationToken);
            return await ProcessResponse<TResponse>(response);
        }
        catch (TaskCanceledException ex)
        {
            _logger.LogError(ex, "Request timed out for endpoint {Endpoint}", endpoint);
            return Result<TResponse, ApiError>.Failure(new ApiError { Message = "Request timed out.", Code = "TIMEOUT", Retryable = true, Exception = ex });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Request failed for endpoint {Endpoint}", endpoint);
            return Result<TResponse, ApiError>.Failure(new ApiError { Message = "An unexpected error occurred.", Code = "UNKNOWN", Exception = ex });
        }
    }

    private async Task<Result<TResponse, ApiError>> ProcessResponse<TResponse>(HttpResponseMessage response)
    {
        if (response.IsSuccessStatusCode)
        {
            try
            {
                if (typeof(TResponse) == typeof(bool) && response.StatusCode == HttpStatusCode.OK)
                {
                    return Result<TResponse, ApiError>.Success((TResponse)(object)true);
                }

                var content = await response.Content.ReadFromJsonAsync<TResponse>();
                if (content != null)
                {
                    return Result<TResponse, ApiError>.Success(content);
                }
                return Result<TResponse, ApiError>.Failure(new ApiError { Message = "Failed to deserialize response.", Code = "DESERIALIZATION_FAILED", StatusCode = (int)response.StatusCode });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Deserialization failed");
                return Result<TResponse, ApiError>.Failure(new ApiError { Message = "Failed to deserialize response.", Code = "DESERIALIZATION_FAILED", Exception = ex });
            }
        }

        var errorMessage = "API error";
        if (response.StatusCode == HttpStatusCode.Unauthorized) errorMessage = "Unauthorized access.";
        else if (response.StatusCode == HttpStatusCode.Forbidden) errorMessage = "Access forbidden.";
        else if (response.StatusCode == HttpStatusCode.InternalServerError) errorMessage = "Internal server error.";

        return Result<TResponse, ApiError>.Failure(new ApiError 
        { 
            Message = errorMessage, 
            StatusCode = (int)response.StatusCode,
            Code = response.StatusCode.ToString()
        });
    }
}
