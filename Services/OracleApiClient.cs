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
        
        string fullUrl = $"{_httpClient.BaseAddress}api/auth/login";
        string redactedMaster = masterToken.Length > 8 ? masterToken.Substring(0, 8) + "..." : "***";
        StartupLogger.LogAuth($"[OracleApiClient] POST {fullUrl}");
        StartupLogger.LogAuth($"[OracleApiClient] Payload: account_id='{request.AccountId}', master_token='{redactedMaster}', device_guid='{request.DeviceGuid}', two_fa_code='{request.TwoFaCode ?? "null"}'");
        foreach (var header in _httpClient.DefaultRequestHeaders)
        {
            StartupLogger.LogAuth($"[OracleApiClient] DefaultHeader: {header.Key} = {string.Join(", ", header.Value)}");
        }
        
        var response = await _httpClient.PostAsJsonAsync("/api/auth/login", request);
        string responseBody = await response.Content.ReadAsStringAsync();
        StartupLogger.LogAuth($"[OracleApiClient] Response Status: {(int)response.StatusCode} ({response.StatusCode})");
        StartupLogger.LogAuth($"[OracleApiClient] Response Body: {responseBody}");
        foreach (var header in response.Headers)
        {
            StartupLogger.LogAuth($"[OracleApiClient] ResponseHeader: {header.Key} = {string.Join(", ", header.Value)}");
        }
        
        if (response.IsSuccessStatusCode)
        {
            var dto = System.Text.Json.JsonSerializer.Deserialize<TokenResponseDto>(responseBody);
            JwtTokens? tokens = null;
            if (dto != null)
            {
                tokens = new JwtTokens(
                    dto.AccessToken,
                    dto.RefreshToken,
                    DateTimeOffset.UtcNow.AddSeconds(dto.ExpiresIn)
                );
                StartupLogger.LogAuth($"[OracleApiClient] Login success. Parsed AccessToken (len={dto.AccessToken.Length}), ExpiresIn={dto.ExpiresIn}");
            }
            else
            {
                StartupLogger.LogAuth("[OracleApiClient] Login success status code, but TokenResponseDto deserialized to null");
            }
            
            return new LoginResult
            {
                Status = LoginStatus.Success,
                Tokens = tokens
            };
        }
        
        ApiErrorResponse? errorBody = null;
        try
        {
            errorBody = System.Text.Json.JsonSerializer.Deserialize<ApiErrorResponse>(responseBody, new System.Text.Json.JsonSerializerOptions { PropertyNameCaseInsensitive = true });
        }
        catch { /* Ignore JSON parse errors on non-JSON response bodies */ }

        if (errorBody?.Code != null)
        {
            StartupLogger.LogAuth($"[OracleApiClient] Structured Error Code received: '{errorBody.Code}', Detail: '{errorBody.Detail}'");
            switch (errorBody.Code.ToUpperInvariant())
            {
                case "DEVICE_LIMIT_EXCEEDED":
                    return new LoginResult 
                    { 
                        Status = LoginStatus.DeviceLimitExceeded,
                        ErrorCode = errorBody.Code,
                        ErrorMessage = errorBody.Detail,
                        DeviceLimitDetails = new DeviceLimitDetails
                        {
                            CurrentDevices = errorBody.CurrentDevices ?? 0,
                            MaxDevices = errorBody.MaxDevices ?? 0,
                            ManageDevicesUrl = errorBody.ManageDevicesUrl ?? ""
                        }
                    };
                case "DEVICE_OWNERSHIP_ERROR":
                    return new LoginResult { Status = LoginStatus.DeviceOwnershipError, ErrorCode = errorBody.Code, ErrorMessage = errorBody.Detail };
                case "DEVICE_DEACTIVATED":
                    return new LoginResult { Status = LoginStatus.DeviceDeactivated, ErrorCode = errorBody.Code, ErrorMessage = errorBody.Detail };
                case "ACCOUNT_DISABLED":
                    return new LoginResult { Status = LoginStatus.AccountDisabled, ErrorCode = errorBody.Code, ErrorMessage = errorBody.Detail };
                case "INVALID_MASTER_TOKEN":
                case "INVALID_CREDENTIALS":
                    return new LoginResult { Status = LoginStatus.InvalidMasterToken, ErrorCode = errorBody.Code, ErrorMessage = errorBody.Detail };
                case "REQUIRES_2FA":
                    return new LoginResult { Status = LoginStatus.Requires2FA, ErrorCode = errorBody.Code, ErrorMessage = errorBody.Detail };
                case "REPLAY_DETECTED":
                    return new LoginResult { Status = LoginStatus.ReplayDetected, ErrorCode = errorBody.Code, ErrorMessage = errorBody.Detail };
            }
        }

        if (response.StatusCode == System.Net.HttpStatusCode.Forbidden)
        {
            if (errorBody?.CurrentDevices != null)
            {
                StartupLogger.LogAuth($"[OracleApiClient] Forbidden fallback -> DeviceLimitExceeded: CurrentDevices={errorBody.CurrentDevices}, MaxDevices={errorBody.MaxDevices}");
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
            StartupLogger.LogAuth("[OracleApiClient] Forbidden fallback -> ReplayDetected");
            return new LoginResult { Status = LoginStatus.ReplayDetected };
        }
        
        if (response.StatusCode == System.Net.HttpStatusCode.Unauthorized)
        {
            StartupLogger.LogAuth($"[OracleApiClient] Unauthorized (401) fallback. Parsed Detail='{errorBody?.Detail}', Requires2Fa={errorBody?.Requires2Fa}");
            if (errorBody?.Requires2Fa == true)
            {
                return new LoginResult 
                { 
                    Status = LoginStatus.Requires2FA 
                };
            }
        }
        
        StartupLogger.LogAuth($"[OracleApiClient] Returning LoginStatus.Error. ReasonPhrase='{response.ReasonPhrase}', Detail='{errorBody?.Detail}'");
        return new LoginResult { Status = LoginStatus.Error, ErrorCode = errorBody?.Code, ErrorMessage = errorBody?.Detail ?? response.ReasonPhrase };
    }



    public async Task<ExchangeResult> ExchangeTokenAsync(string exchangeToken, string deviceGuid)
    {
        var request = new ExchangeRequestDto
        {
            ExchangeToken = exchangeToken,
            DeviceGuid = deviceGuid
        };
        string fullUrl = $"{_httpClient.BaseAddress}api/auth/exchange";
        StartupLogger.LogAuth($"[OracleApiClient] POST {fullUrl}. device_guid='{deviceGuid}'");
        var response = await _httpClient.PostAsJsonAsync("/api/auth/exchange", request);
        string responseBody = await response.Content.ReadAsStringAsync();
        StartupLogger.LogAuth($"[OracleApiClient] Exchange Response Status: {(int)response.StatusCode} ({response.StatusCode}), Body: {responseBody}");
        if (response.IsSuccessStatusCode)
        {
            var dto = System.Text.Json.JsonSerializer.Deserialize<ExchangeResponseDto>(responseBody);
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
        string fullUrl = $"{_httpClient.BaseAddress}api/client/config";
        StartupLogger.LogAuth($"[OracleApiClient] GET {fullUrl} with X-Device-ID='{deviceGuid}'");
        
        var response = await _httpClient.SendAsync(request);
        string responseBody = await response.Content.ReadAsStringAsync();
        StartupLogger.LogAuth($"[OracleApiClient] FetchClientConfig Status: {(int)response.StatusCode} ({response.StatusCode}), Body: {responseBody}");
        if (response.IsSuccessStatusCode)
        {
            return System.Text.Json.JsonSerializer.Deserialize<ClientConfigResponse>(responseBody, new System.Text.Json.JsonSerializerOptions { PropertyNameCaseInsensitive = true });
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
