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

    public bool IsAuthenticated =>
        _tokenService.GetCurrentState() == SessionState.Authenticated || 
        _tokenService.GetCurrentState() == SessionState.Offline;

    public string GetOrCreateDeviceGuid()
    {
        return _secureStorage.GetDeviceGuid();
    }

    public async Task<LoginResult> LoginAsync(string accountId, string masterToken)
    {
        _secureStorage.SaveMasterToken(masterToken);
        
        var deviceId = _secureStorage.GetDeviceGuid();
        var osVersion = Environment.OSVersion.Version.ToString();
        var clientVersion = System.Reflection.Assembly.GetExecutingAssembly().GetName().Version?.ToString() ?? "1.0.0";
        var device = new DeviceRegistration(deviceId, Environment.MachineName, "windows", clientVersion, osVersion);
        var result = await _apiClient.LoginAsync(accountId, masterToken, device);

        if (result.Status == LoginStatus.Success && result.Tokens != null)
        {
            _tokenService.UpdateTokens(result.Tokens);
            _secureStorage.SaveLastTrustedTimestamp(DateTimeOffset.UtcNow);
            
            // Fetch license immediately upon success
            var license = await _apiClient.FetchLicenseAsync(result.Tokens.AccessToken);
            if (license != null)
            {
                _licenseService.UpdateLicenseBlob(license);
            }
        }

        return result;
    }

    public async Task<bool> Verify2FaAsync(string tempToken, string totpCode)
    {
        var tokens = await _apiClient.Verify2FaAsync(tempToken, totpCode);
        if (tokens != null)
        {
            _tokenService.UpdateTokens(tokens);
            _secureStorage.SaveLastTrustedTimestamp(DateTimeOffset.UtcNow);
            
            var license = await _apiClient.FetchLicenseAsync(tokens.AccessToken);
            if (license != null)
            {
                _licenseService.UpdateLicenseBlob(license);
            }
            return true;
        }
        return false;
    }

    public void Logout()
    {
        _tokenService.ClearTokens();
        _secureStorage.ClearAll();
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
