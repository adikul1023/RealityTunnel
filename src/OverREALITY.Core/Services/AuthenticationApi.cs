using System;
using System.Net;
using System.Net.Http;
using System.Net.Http.Json;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using OverREALITY.Shared.Api.Authentication;
using OverREALITY.Shared.Errors;
using OverREALITY.Shared.Interfaces;

namespace OverREALITY.Core.Services;

public class AuthenticationApi : IAuthenticationApi
{
    private readonly HttpClient _httpClient;
    private readonly ILogger<AuthenticationApi> _logger;

    public AuthenticationApi(HttpClient httpClient, IDomainResolver domainResolver, ILogger<AuthenticationApi> logger)
    {
        _httpClient = httpClient;
        _logger = logger;
        
        _httpClient.BaseAddress = new Uri(domainResolver.ApiBaseUrl);
        _httpClient.Timeout = TimeSpan.FromSeconds(30);
    }

    public async Task<Result<LoginResponse, AuthenticationError>> LoginAsync(LoginRequest request, CancellationToken cancellationToken = default)
    {
        return await PostAsync("/api/auth/login", request, cancellationToken);
    }

    public async Task<Result<LoginResponse, AuthenticationError>> RefreshAsync(RefreshRequest request, CancellationToken cancellationToken = default)
    {
        return await PostAsync("/api/auth/refresh", request, cancellationToken);
    }

    private async Task<Result<LoginResponse, AuthenticationError>> PostAsync(string endpoint, object payload, CancellationToken cancellationToken)
    {
        try
        {
            _logger.LogDebug("AUTH REQUEST: URL={URL}", endpoint);

            var response = await _httpClient.PostAsJsonAsync(endpoint, payload, cancellationToken: cancellationToken);
            var responseContent = await response.Content.ReadAsStringAsync(cancellationToken);
            _logger.LogDebug("AUTH RESPONSE: Status={Status}", response.StatusCode);

            if (response.IsSuccessStatusCode)
            {
                var content = System.Text.Json.JsonSerializer.Deserialize<LoginResponse>(responseContent, new System.Text.Json.JsonSerializerOptions { PropertyNameCaseInsensitive = true });
                if (content != null)
                {
                    return Result<LoginResponse, AuthenticationError>.Success(content);
                }
                return Result<LoginResponse, AuthenticationError>.Failure(new AuthenticationError { Message = "Failed to deserialize response.", Code = "DESERIALIZATION_FAILED", StatusCode = (int)response.StatusCode });
            }

            var errorMessage = "API error";
            var errorCode = response.StatusCode.ToString();
            try 
            {
                var errorObj = System.Text.Json.JsonDocument.Parse(responseContent);
                var root = errorObj.RootElement;
                
                if (root.TryGetProperty("message", out var msgProp) || root.TryGetProperty("detail", out msgProp))
                {
                    if (msgProp.ValueKind == System.Text.Json.JsonValueKind.String)
                    {
                        errorMessage = msgProp.GetString() ?? responseContent;
                    }
                    else if (msgProp.ValueKind == System.Text.Json.JsonValueKind.Object)
                    {
                        if (msgProp.TryGetProperty("detail", out var innerMsgProp) || msgProp.TryGetProperty("message", out innerMsgProp))
                        {
                            errorMessage = innerMsgProp.GetString() ?? responseContent;
                        }
                        if (msgProp.TryGetProperty("code", out var innerCodeProp))
                        {
                            errorCode = innerCodeProp.GetString() ?? errorCode;
                        }
                    }
                }
                
                if (root.TryGetProperty("code", out var codeProp) && codeProp.ValueKind == System.Text.Json.JsonValueKind.String)
                {
                    errorCode = codeProp.GetString() ?? errorCode;
                }
            } 
            catch 
            {
                errorMessage = responseContent;
            }

            return Result<LoginResponse, AuthenticationError>.Failure(new AuthenticationError 
            { 
                Message = errorMessage, 
                StatusCode = (int)response.StatusCode,
                Code = errorCode
            });
        }
        catch (TaskCanceledException ex)
        {
            _logger.LogError(ex, "Request timed out for {Endpoint}", endpoint);
            return Result<LoginResponse, AuthenticationError>.Failure(new AuthenticationError { Message = "Request timed out.", Code = "TIMEOUT", Retryable = true, Exception = ex });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Request failed for {Endpoint}", endpoint);
            return Result<LoginResponse, AuthenticationError>.Failure(new AuthenticationError { Message = "An unexpected error occurred.", Code = "UNKNOWN", Exception = ex });
        }
    }
}
