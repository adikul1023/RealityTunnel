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
    private readonly ILogger<TokenProvider> _logger;
    private string? _cachedAccessToken;

    public TokenProvider(ISecureStorage secureStorage, IAuthenticationApi authApi, ILogger<TokenProvider> logger)
    {
        _secureStorage = secureStorage;
        _authApi = authApi;
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
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to refresh token");
        }
        
        return null;
    }
}
