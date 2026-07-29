using System;
using System.IdentityModel.Tokens.Jwt;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using OverREALITY.Shared.Interfaces;
using OverREALITY.Shared.Api.Authentication;

namespace OverREALITY.Core.Services;

public class TokenProvider : ITokenProvider
{
    private readonly ISecureStorage _secureStorage;
    private readonly IAuthenticationApi _authApi;
    private readonly ISessionManager _sessionManager;
    private readonly ILogger<TokenProvider> _logger;
    private string? _cachedAccessToken;

    public TokenProvider(ISecureStorage secureStorage, IAuthenticationApi authApi, ISessionManager sessionManager, ILogger<TokenProvider> logger)
    {
        _secureStorage = secureStorage;
        _authApi = authApi;
        _sessionManager = sessionManager;
        _logger = logger;
    }

    public async Task<string?> GetValidTokenAsync(CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrEmpty(_cachedAccessToken))
        {
            _cachedAccessToken = await _secureStorage.GetSecureAsync("AccessToken");
        }

        if (string.IsNullOrEmpty(_cachedAccessToken))
            return null;

        var handler = new JwtSecurityTokenHandler();
        if (handler.CanReadToken(_cachedAccessToken))
        {
            var jwtToken = handler.ReadJwtToken(_cachedAccessToken);
            if (jwtToken.ValidTo > DateTime.UtcNow.AddMinutes(1))
            {
                return _cachedAccessToken;
            }
        }

        return await RefreshTokenAsync(cancellationToken);
    }

    public void InvalidateToken()
    {
        _cachedAccessToken = null;
    }

    private async Task<string?> RefreshTokenAsync(CancellationToken cancellationToken)
    {
        try
        {
            var refreshToken = await _secureStorage.GetSecureAsync("RefreshToken");
            if (string.IsNullOrEmpty(refreshToken))
                return null;

            var response = await _authApi.RefreshAsync(new RefreshRequest { RefreshToken = refreshToken }, cancellationToken);

            if (response.IsSuccess && response.Value != null)
            {
                _cachedAccessToken = response.Value.AccessToken;
                await _secureStorage.SaveSecureAsync("AccessToken", response.Value.AccessToken);
                await _secureStorage.SaveSecureAsync("RefreshToken", response.Value.RefreshToken);
                return response.Value.AccessToken;
            }
            else if (!response.IsSuccess && (response.Error?.Code == "DEVICE_REVOKED" || response.Error?.Code == "REPLAY_DETECTED" || response.Error?.Code == "INVALID_TOKEN"))
            {
                _logger.LogWarning("Fatal error during token refresh: {ErrorCode}. Clearing session.", response.Error?.Code);
                InvalidateToken();
                await _secureStorage.DeleteSecureAsync("AccessToken");
                await _secureStorage.DeleteSecureAsync("RefreshToken");
                _sessionManager.ClearSession();
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to refresh token");
        }
        
        return null;
    }
}
