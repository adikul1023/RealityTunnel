using System.Threading.Tasks;
using RealityTunnel.Models;

namespace RealityTunnel.Services;

public class ConfigurationProvider
{
    private readonly LicenseService _licenseService;
    private readonly SecureStorageService _storage;
    private readonly AuthenticationService _authService;
    private readonly OracleApiClient _apiClient;

    public ConfigurationProvider(LicenseService licenseService, SecureStorageService storage, AuthenticationService authService, OracleApiClient apiClient)
    {
        _licenseService = licenseService;
        _storage = storage;
        _authService = authService;
        _apiClient = apiClient;
    }

    public VpnProfile? GetCachedProfile()
    {
        return _storage.GetVpnProfile();
    }

    public async Task RefreshProfileBackgroundAsync()
    {
        await RefreshProfileFromNetworkAsync();
    }

    public async Task<VpnProfile?> GetVpnProfileAsync()
    {
        var cachedProfile = _storage.GetVpnProfile();
        if (cachedProfile != null && _licenseService.IsGracePeriodValid())
        {
            _ = RefreshProfileFromNetworkAsync();
            return cachedProfile;
        }

        return await RefreshProfileFromNetworkAsync();
    }

    private async Task<VpnProfile?> RefreshProfileFromNetworkAsync()
    {
        string? token = await _authService.GetValidAccessTokenAsync();
        if (!string.IsNullOrEmpty(token))
        {
            try
            {
                string deviceGuid = _storage.GetDeviceGuid();
                var config = await _apiClient.FetchClientConfigAsync(token, deviceGuid);
                if (config != null)
                {
                    _storage.SaveVpnProfile(config.VpnProfile);
                    // Also save the license blob for offline validation
                    var licenseBlob = new LicenseBlob(config.LicenseBlob.Payload, config.LicenseBlob.Signature);
                    _storage.SaveLicenseBlob(licenseBlob);
                    
                    return config.VpnProfile;
                }
            }
            catch
            {
                // Network error, fallback to cache
            }
        }

        return null;
    }
}
