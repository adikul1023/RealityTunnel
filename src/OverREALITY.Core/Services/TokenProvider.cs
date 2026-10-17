using System;
using System.IdentityModel.Tokens.Jwt;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using OverREALITY.Shared.Interfaces;
using OverREALITY.Shared.Api.Authentication;
using OverREALITY.Shared.Errors;

namespace OverREALITY.Core.Services;

public class TokenProvider : ITokenProvider
{
    private readonly ISecureStorage _secureStorage;
    private readonly IAuthenticationApi _authApi;
    private readonly ISessionManager _sessionManager;
    private readonly ILogger<TokenProvider> _logger;
    private readonly SemaphoreSlim _refreshLock = new(1, 1);
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

        if (IsTokenValid(_cachedAccessToken))
        {
            return _cachedAccessToken;
        }

        await _refreshLock.WaitAsync(cancellationToken);
        try
        {
            // Re-check after acquiring lock in case another concurrent operation just refreshed it
            if (string.IsNullOrEmpty(_cachedAccessToken))
            {
                _cachedAccessToken = await _secureStorage.GetSecureAsync("AccessToken");
            }

            if (IsTokenValid(_cachedAccessToken))
            {
                return _cachedAccessToken;
            }

            var refreshedToken = await RefreshTokenAsync(cancellationToken);
            if (!string.IsNullOrEmpty(refreshedToken))
            {
                _cachedAccessToken = refreshedToken;
            }
            return refreshedToken;
        }
        finally
        {
            _refreshLock.Release();
        }
    }

    public void InvalidateToken()
    {
        _cachedAccessToken = null;
    }

    private static bool IsTokenValid(string? token)
    {
        if (string.IsNullOrEmpty(token))
            return false;

        var handler = new JwtSecurityTokenHandler();
        if (handler.CanReadToken(token))
        {
            var jwtToken = handler.ReadJwtToken(token);
            if (jwtToken.ValidTo > DateTime.UtcNow.AddMinutes(1))
            {
                return true;
            }
        }

        return false;
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
            else if (!response.IsSuccess && IsFatalRejection(response.Error))
            {
                _logger.LogWarning("Fatal error during token refresh: {ErrorCode} (Status {StatusCode}). Clearing session.", response.Error?.Code, response.Error?.StatusCode);
                InvalidateToken();
                await _secureStorage.DeleteSecureAsync("AccessToken");
                await _secureStorage.DeleteSecureAsync("RefreshToken");
                await _secureStorage.DeleteSecureAsync("account_id");
                _sessionManager.ClearSession();
            }
            else
            {
                _logger.LogWarning("Transient or non-fatal error during token refresh: {ErrorCode} (Status {StatusCode}). Preserving stored session.", response.Error?.Code, response.Error?.StatusCode);
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to refresh token");
        }
        
        return null;
    }

    private static bool IsFatalRejection(AuthenticationError? error)
    {
        if (error == null) return false;

        if (error.StatusCode == 401) return true;

        var code = error.Code?.ToUpperInvariant();
        return code is "DEVICE_REVOKED" or "DEVICE_DEACTIVATED" or "REPLAY_DETECTED" or "INVALID_TOKEN" or "AUTH_ERROR" or "ACCOUNT_DISABLED" or "UNAUTHORIZED";
    }
}
