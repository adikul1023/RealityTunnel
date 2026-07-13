using System;
using System.Threading.Tasks;
using RealityTunnel.Models;

namespace RealityTunnel.Services;

public class AuthenticationService
{
    private readonly OracleApiClient _apiClient;
    private readonly TokenService _tokenService;
    private readonly SecureStorageService _secureStorage;
    private readonly LicenseService _licenseService;
    private readonly object _refreshLock = new object();
    private Task<string?>? _currentRefreshTask;

    public AuthenticationService(OracleApiClient apiClient, TokenService tokenService, SecureStorageService secureStorage, LicenseService licenseService)
    {
        _apiClient = apiClient;
        _tokenService = tokenService;
        _secureStorage = secureStorage;
        _licenseService = licenseService;
    }

    public bool IsAuthenticated => _tokenService.CurrentTokens != null;

    public string GetOrCreateDeviceGuid()
    {
        return _secureStorage.GetDeviceGuid();
    }

    public async Task<LoginResult> LoginAsync(string stealthyCredential, string? totpCode = null)
    {
        if (string.IsNullOrWhiteSpace(stealthyCredential))
        {
            return new LoginResult { Status = LoginStatus.Error, ErrorMessage = "Credential cannot be empty." };
        }

        var parts = stealthyCredential.Split(':', 2);
        if (parts.Length != 2)
        {
            return new LoginResult { Status = LoginStatus.Error, ErrorMessage = "Invalid credential format. Expected AccountID:MasterToken." };
        }

        string accountId = parts[0].Trim();
        string masterToken = parts[1].Trim();
        
        var deviceId = _secureStorage.GetDeviceGuid();
        var osVersion = Environment.OSVersion.Version.ToString();
        var clientVersion = System.Reflection.Assembly.GetExecutingAssembly().GetName().Version?.ToString() ?? "1.0.0";
        var device = new DeviceRegistration(deviceId, Environment.MachineName, "windows", clientVersion, osVersion);
        var result = await _apiClient.LoginAsync(accountId, masterToken, device, totpCode);

        if (result.Status == LoginStatus.Success && result.Tokens != null)
        {
            _tokenService.UpdateTokens(result.Tokens);
            _secureStorage.SaveLastTrustedTimestamp(DateTimeOffset.UtcNow);
            _secureStorage.SaveAccountId(accountId);
            // Fetch config immediately upon success
            string deviceGuid = _secureStorage.GetDeviceGuid();
            var config = await _apiClient.FetchClientConfigAsync(result.Tokens.AccessToken, deviceGuid);
            if (config != null)
            {
                var license = new LicenseBlob(config.LicenseBlob.Payload, config.LicenseBlob.Signature);
                _licenseService.UpdateLicenseBlob(license);
                _secureStorage.SaveVpnProfile(config.VpnProfile);
            }
        }

        return result;
    }

    public void Logout()
    {
        _tokenService.ClearTokens();
        // ClearTokens() internally calls _storage.ClearSession() which clears all session
        // files while deliberately preserving device_guid.dat
    }

    public async Task RefreshTokenIfNeededAsync()
    {
        await GetValidAccessTokenAsync();
    }

    public async Task<string?> GetValidAccessTokenAsync()
    {
        var state = _tokenService.GetCurrentState();
        var tokens = _tokenService.GetCurrentTokens();

        if (state == SessionState.Offline || tokens == null)
            return null;

        if (state == SessionState.Authenticated && DateTimeOffset.UtcNow < tokens.ExpiresAt.AddMinutes(-5))
        {
            return tokens.AccessToken;
        }

        Task<string?> taskToAwait;
        lock (_refreshLock)
        {
            if (_currentRefreshTask != null)
            {
                taskToAwait = _currentRefreshTask;
            }
            else
            {
                _currentRefreshTask = PerformRefreshAsync(tokens.RefreshToken);
                taskToAwait = _currentRefreshTask;
            }
        }

        try
        {
            return await taskToAwait;
        }
        finally
        {
            lock (_refreshLock)
            {
                if (_currentRefreshTask == taskToAwait)
                {
                    _currentRefreshTask = null;
                }
            }
        }
    }

    private async Task<string?> PerformRefreshAsync(string refreshToken)
    {
        try
        {
            var newTokens = await _apiClient.RefreshAsync(refreshToken);
            if (newTokens != null)
            {
                _tokenService.UpdateTokens(newTokens);
                _secureStorage.SaveLastTrustedTimestamp(DateTimeOffset.UtcNow);
                return newTokens.AccessToken;
            }
        }
        catch (SessionRevokedException)
        {
            _tokenService.ClearTokens();
            throw;
        }
        catch (UnauthorizedAccessException ex) when (ex.Message == "ReplayDetected")
        {
            _tokenService.HandleReplayDetected();
            throw;
        }
        catch
        {
        }
        return null;
    }
}
