using System;
using System.Net.Http;
using System.Net.Http.Json;
using System.Threading.Tasks;
using RealityTunnel.Models;

namespace RealityTunnel.Services;

public class OracleApiClient
{
    private readonly HttpClient _httpClient;

    public OracleApiClient(HttpClient httpClient)
    {
        _httpClient = httpClient;
    }

    public async Task<LoginResult> LoginAsync(string accountId, string masterToken, DeviceRegistration device)
    {
        var request = new LoginRequest
        {
            AccountId = accountId, 
            MasterToken = masterToken,
            DeviceGuid = device.DeviceGuid
        };
        
        var response = await _httpClient.PostAsJsonAsync("/api/auth/login", request);
        
        if (response.IsSuccessStatusCode)
        {
            return new LoginResult
            {
                Status = LoginStatus.Success,
                Tokens = await response.Content.ReadFromJsonAsync<JwtTokens>()
            };
        }
        
        if (response.StatusCode == System.Net.HttpStatusCode.Forbidden)
        {
            return new LoginResult { Status = LoginStatus.ReplayDetected };
        }
        
        if (response.StatusCode == System.Net.HttpStatusCode.Unauthorized)
        {
            var errorBody = await response.Content.ReadFromJsonAsync<ApiErrorResponse>();
            if (errorBody?.Error == "requires_2fa")
            {
                return new LoginResult 
                { 
                    Status = LoginStatus.Requires2FA,
                    TemporaryLoginToken = errorBody.TemporaryLoginToken
                };
            }
        }
        
        if (response.StatusCode == System.Net.HttpStatusCode.Conflict || response.StatusCode == System.Net.HttpStatusCode.BadRequest)
        {
            var errorBody = await response.Content.ReadFromJsonAsync<ApiErrorResponse>();
            if (errorBody?.Error == "device_limit_exceeded")
            {
                return new LoginResult 
                { 
                    Status = LoginStatus.DeviceLimitExceeded,
                    DeviceLimitDetails = new DeviceLimitDetails
                    {
                        CurrentDevices = errorBody.CurrentDevices ?? 0,
                        MaxDevices = errorBody.MaxDevices ?? 0,
                        ManageDevicesUrl = errorBody.ManageDevicesUrl ?? ""
                    }
                };
            }
        }
        
        return new LoginResult { Status = LoginStatus.Error, ErrorMessage = response.ReasonPhrase };
    }

    public async Task<JwtTokens?> Verify2FaAsync(string tempToken, string totpCode)
    {
        var request = new Verify2FaRequest
        {
            TemporaryLoginToken = tempToken,
            TotpCode = totpCode
        };
        
        var response = await _httpClient.PostAsJsonAsync("/api/auth/verify-2fa", request);
        if (response.IsSuccessStatusCode)
        {
            return await response.Content.ReadFromJsonAsync<JwtTokens>();
        }
        return null;
    }

    public async Task<ExchangeResult> ExchangeTokenAsync(string exchangeToken, string deviceGuid)
    {
        var request = new ExchangeRequestDto
        {
            ExchangeToken = exchangeToken,
            DeviceGuid = deviceGuid
        };
        var response = await _httpClient.PostAsJsonAsync("/api/auth/exchange", request);
        if (response.IsSuccessStatusCode)
        {
            var dto = await response.Content.ReadFromJsonAsync<ExchangeResponseDto>();
            if (dto != null)
            {
                var tokens = new JwtTokens(
                    dto.AccessToken,
                    dto.RefreshToken,
                    DateTimeOffset.UtcNow.AddSeconds(dto.ExpiresIn)
                );
                return new ExchangeResult
                {
                    Success = true,
                    Tokens = tokens,
                    IsInitialProvisioning = dto.IsInitialProvisioning
                };
            }
        }
        return new ExchangeResult { Success = false, ErrorMessage = response.ReasonPhrase };
    }

    public async Task<JwtTokens?> RefreshAsync(string refreshToken)
    {
        var request = new RefreshRequest { RefreshToken = refreshToken };
        var response = await _httpClient.PostAsJsonAsync("/api/auth/refresh", request);
        
        if (response.IsSuccessStatusCode)
        {
            return await response.Content.ReadFromJsonAsync<JwtTokens>();
        }
        
        if (response.StatusCode == System.Net.HttpStatusCode.Forbidden)
        {
            throw new UnauthorizedAccessException("ReplayDetected");
        }
        
        return null;
    }

    public async Task<LicenseBlob?> FetchLicenseAsync(string accessToken)
    {
        _httpClient.DefaultRequestHeaders.Authorization = new System.Net.Http.Headers.AuthenticationHeaderValue("Bearer", accessToken);
        var response = await _httpClient.GetAsync("/api/client/license");
        if (response.IsSuccessStatusCode)
        {
            return await response.Content.ReadFromJsonAsync<LicenseBlob>();
        }
        return null;
    }
    
    public async Task<VpnProfile?> FetchVpnProfileAsync(string accessToken)
    {
        _httpClient.DefaultRequestHeaders.Authorization = new System.Net.Http.Headers.AuthenticationHeaderValue("Bearer", accessToken);
        var response = await _httpClient.GetAsync("/api/client/profile");
        if (response.IsSuccessStatusCode)
        {
            return await response.Content.ReadFromJsonAsync<VpnProfile>();
        }
        return null;
    }

    public async Task<ClientMeResponse?> FetchClientMeAsync(string accessToken)
    {
        _httpClient.DefaultRequestHeaders.Authorization = new System.Net.Http.Headers.AuthenticationHeaderValue("Bearer", accessToken);
        var response = await _httpClient.GetAsync("/api/client/me");
        if (response.IsSuccessStatusCode)
        {
            return await response.Content.ReadFromJsonAsync<ClientMeResponse>();
        }
        return null;
    }

    public async Task<ClientUpdate?> FetchClientUpdateAsync()
    {
        var response = await _httpClient.GetAsync("/api/client/update");
        if (response.IsSuccessStatusCode)
        {
            return await response.Content.ReadFromJsonAsync<ClientUpdate>();
        }
        return null;
    }
}
