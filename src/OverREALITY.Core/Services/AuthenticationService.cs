using System;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using OverREALITY.Shared.Errors;
using OverREALITY.Shared.Interfaces;
using OverREALITY.Shared.Api.Authentication;
using OverREALITY.Shared.Domain.Session;

namespace OverREALITY.Core.Services;

public class AuthenticationService : IAuthService
{
    private readonly IAuthenticationApi _authApi;
    private readonly ISecureStorage _secureStorage;
    private readonly ISessionManager _sessionManager;
    private readonly ITokenProvider _tokenProvider;
    private readonly ISessionFactory _sessionFactory;
    private readonly ILogger<AuthenticationService> _logger;

    public AuthenticationService(IAuthenticationApi authApi, ISecureStorage secureStorage, ISessionManager sessionManager, ITokenProvider tokenProvider, ISessionFactory sessionFactory, ILogger<AuthenticationService> logger)
    {
        _authApi = authApi;
        _secureStorage = secureStorage;
        _sessionManager = sessionManager;
        _tokenProvider = tokenProvider;
        _sessionFactory = sessionFactory;
        _logger = logger;
    }

    public async Task<Result<LoginResponse, AuthenticationError>> LoginAsync(string accountId, string masterToken, CancellationToken cancellationToken = default)
    {
        var deviceGuid = await _secureStorage.GetSecureAsync("device_guid");
        if (string.IsNullOrEmpty(deviceGuid))
        {
            deviceGuid = Guid.NewGuid().ToString();
            await _secureStorage.SaveSecureAsync("device_guid", deviceGuid);
        }

        var result = await _authApi.LoginAsync(new LoginRequest { AccountId = accountId, MasterToken = masterToken, DeviceGuid = deviceGuid, ClientType = "desktop" }, cancellationToken);
        
        if (!result.IsSuccess && result.Error?.Code == "DEVICE_DEACTIVATED")
        {
            _logger.LogWarning("Device was deactivated. Generating a new Device GUID and retrying...");
            deviceGuid = Guid.NewGuid().ToString();
            await _secureStorage.SaveSecureAsync("device_guid", deviceGuid);
            result = await _authApi.LoginAsync(new LoginRequest { AccountId = accountId, MasterToken = masterToken, DeviceGuid = deviceGuid, ClientType = "desktop" }, cancellationToken);
        }
        
        if (result.IsSuccess && result.Value != null)
        {
            try
            {
                await _secureStorage.SaveSecureAsync("AccessToken", result.Value.AccessToken);
                await _secureStorage.SaveSecureAsync("RefreshToken", result.Value.RefreshToken);
                await _secureStorage.SaveSecureAsync("account_id", accountId);

                var session = _sessionFactory.Create(result.Value.AccessToken, accountId);
                _sessionManager.UpdateSession(session);

                return Result<LoginResponse, AuthenticationError>.Success(result.Value);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to store secure credentials");
                return Result<LoginResponse, AuthenticationError>.Failure(new AuthenticationError { Message = "Failed to securely store credentials", Exception = ex });
            }
        }

        return Result<LoginResponse, AuthenticationError>.Failure(new AuthenticationError { 
            Message = result.Error?.Message ?? "Login failed",
            Code = result.Error?.Code ?? "LOGIN_FAILED",
            StatusCode = result.Error?.StatusCode ?? 0
        });
    }

    public async Task<Result<bool, AuthenticationError>> LogoutAsync(CancellationToken cancellationToken = default)
    {
        await _secureStorage.DeleteSecureAsync("AccessToken");
        await _secureStorage.DeleteSecureAsync("RefreshToken");
        await _secureStorage.DeleteSecureAsync("account_id");
        _tokenProvider.InvalidateToken();
        _sessionManager.ClearSession();
        return Result<bool, AuthenticationError>.Success(true);
    }

    public async Task<Result<string, AuthenticationError>> GetValidAccessTokenAsync(CancellationToken cancellationToken = default)
    {
        var token = await _tokenProvider.GetValidTokenAsync(cancellationToken);
        if (string.IsNullOrEmpty(token))
        {
            return Result<string, AuthenticationError>.Failure(new AuthenticationError { Message = "No valid token available", Code = "NO_TOKEN" });
        }
        return Result<string, AuthenticationError>.Success(token);
    }

    public async Task<bool> TryRestoreSessionAsync(CancellationToken cancellationToken = default)
    {
        try
        {
            var token = await _tokenProvider.GetValidTokenAsync(cancellationToken);
            if (!string.IsNullOrEmpty(token))
            {
                var accountId = await _secureStorage.GetSecureAsync("account_id");
                if (string.IsNullOrEmpty(accountId))
                {
                    var handler = new System.IdentityModel.Tokens.Jwt.JwtSecurityTokenHandler();
                    if (handler.CanReadToken(token))
                    {
                        var jwt = handler.ReadJwtToken(token);
                        accountId = jwt.Claims.FirstOrDefault(c => c.Type == "account")?.Value;
                        if (!string.IsNullOrEmpty(accountId))
                        {
                            await _secureStorage.SaveSecureAsync("account_id", accountId);
                        }
                    }
                }

                if (!string.IsNullOrEmpty(accountId))
                {
                    var session = _sessionFactory.Create(token, accountId);
                    _sessionManager.UpdateSession(session);
                    return true;
                }
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to restore session.");
        }
        return false;
    }
}
