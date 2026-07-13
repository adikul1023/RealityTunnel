using System;
using System.Net.Http;
using System.Net.Http.Json;
using System.Threading.Tasks;
using System.Text.Json.Serialization;
using RealityTunnel.Models;

namespace RealityTunnel.Services;

public class OracleApiClient
{
    private readonly HttpClient _httpClient;

    private class TokenResponseDto
    {
        [JsonPropertyName("access_token")]
        public string AccessToken { get; set; } = string.Empty;

        [JsonPropertyName("refresh_token")]
        public string RefreshToken { get; set; } = string.Empty;

        [JsonPropertyName("expires_in")]
        public int ExpiresIn { get; set; }
    }

    public OracleApiClient(HttpClient httpClient)
    {
        _httpClient = httpClient;
    }

    public async Task<LoginResult> LoginAsync(string accountId, string masterToken, DeviceRegistration device, string? totpCode = null)
    {
        var request = new LoginRequest
        {
            AccountId = accountId, 
            MasterToken = masterToken,
            DeviceGuid = device.DeviceGuid,
            TwoFaCode = totpCode
        };
        
        var response = await _httpClient.PostAsJsonAsync("/api/auth/login", request);
        
        if (response.IsSuccessStatusCode)
        {
            var dto = await response.Content.ReadFromJsonAsync<TokenResponseDto>();
            JwtTokens? tokens = null;
            if (dto != null)
            {
                tokens = new JwtTokens(
                    dto.AccessToken,
                    dto.RefreshToken,
                    DateTimeOffset.UtcNow.AddSeconds(dto.ExpiresIn)
                );
            }
            
            return new LoginResult
            {
                Status = LoginStatus.Success,
                Tokens = tokens
            };
        }
        
        if (response.StatusCode == System.Net.HttpStatusCode.Forbidden)
        {
            return new LoginResult { Status = LoginStatus.ReplayDetected };
        }
        
        if (response.StatusCode == System.Net.HttpStatusCode.Unauthorized)
        {
            var errorBody = await response.Content.ReadFromJsonAsync<ApiErrorResponse>();
            if (errorBody?.Requires2Fa == true)
            {
                return new LoginResult 
                { 
                    Status = LoginStatus.Requires2FA 
                };
            }
        }
        
        if (response.StatusCode == System.Net.HttpStatusCode.Forbidden)
        {
            var errorBody = await response.Content.ReadFromJsonAsync<ApiErrorResponse>();
            if (errorBody?.CurrentDevices != null)
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
            var dto = await response.Content.ReadFromJsonAsync<TokenResponseDto>();
            if (dto != null)
            {
                return new JwtTokens(
                    dto.AccessToken,
                    dto.RefreshToken,
                    DateTimeOffset.UtcNow.AddSeconds(dto.ExpiresIn)
                );
            }
            return null;
        }
        
        if (response.StatusCode == System.Net.HttpStatusCode.Unauthorized)
        {
            var json = await response.Content.ReadAsStringAsync();
            if (json.Contains("\"DEVICE_REVOKED\"") || json.Contains("\"REPLAY_DETECTED\""))
            {
                throw new SessionRevokedException();
            }
        }
        
        if (response.StatusCode == System.Net.HttpStatusCode.Forbidden)
        {
            throw new SessionRevokedException("ReplayDetected"); // Keep this for backwards compatibility if needed
        }
        
        return null;
    }

    public async Task<ClientConfigResponse?> FetchClientConfigAsync(string accessToken, string deviceGuid)
    {
        _httpClient.DefaultRequestHeaders.Authorization = new System.Net.Http.Headers.AuthenticationHeaderValue("Bearer", accessToken);
        
        var request = new HttpRequestMessage(HttpMethod.Get, "/api/client/config");
        request.Headers.Add("X-Device-ID", deviceGuid);
        
        var response = await _httpClient.SendAsync(request);
        if (response.IsSuccessStatusCode)
        {
            return await response.Content.ReadFromJsonAsync<ClientConfigResponse>();
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

    public async Task<DeviceStatusResponse?> CheckDeviceStatusAsync(string accessToken, string deviceGuid, System.Threading.CancellationToken cancellationToken = default)
    {
        using var request = new HttpRequestMessage(HttpMethod.Get, "/api/devices/status");
        request.Headers.Authorization = new System.Net.Http.Headers.AuthenticationHeaderValue("Bearer", accessToken);
        request.Headers.Add("X-Device-Guid", deviceGuid);

        var response = await _httpClient.SendAsync(request, cancellationToken);
        if (response.IsSuccessStatusCode)
        {
            return await response.Content.ReadFromJsonAsync<DeviceStatusResponse>(cancellationToken: cancellationToken);
        }
        return null;
    }
}
