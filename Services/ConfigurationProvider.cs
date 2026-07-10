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
                var remoteProfile = await _apiClient.FetchVpnProfileAsync(token);
                if (remoteProfile != null)
                {
                    _storage.SaveVpnProfile(remoteProfile);
                    return remoteProfile;
                }
            }
            catch
            {
                // Network error, fallback to cache
            }
        }

#if DEBUG
        var settings = AppSettings.Load();
        if (!string.IsNullOrWhiteSpace(settings.ServerIp))
        {
            return new VpnProfile 
            { 
                ServerIp = settings.ServerIp,
                Uuid = "00000000-0000-0000-0000-000000000000",
                PublicKey = "dummy-key",
                Sni = "www.microsoft.com"
            };
        }
#endif

        return null;
    }
}
