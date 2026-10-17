using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.IdentityModel.Tokens.Jwt;
using System.Linq;
using System.Security.Claims;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging.Abstractions;
using Microsoft.IdentityModel.Tokens;
using Moq;
using OverREALITY.Core.Services;
using OverREALITY.Shared.Api.Authentication;
using OverREALITY.Shared.Errors;
using OverREALITY.Shared.Interfaces;
using Xunit;

namespace OverREALITY.Tests.Core;

public class TokenProviderTests
{
    private static string CreateJwt(DateTime expiresAt)
    {
        var tokenDescriptor = new SecurityTokenDescriptor
        {
            Subject = new ClaimsIdentity(new[] { new Claim("sub", "user-uuid"), new Claim("account", "RT-USER-1001") }),
            NotBefore = expiresAt.AddMinutes(-15),
            IssuedAt = expiresAt.AddMinutes(-15),
            Expires = expiresAt,
            SigningCredentials = new SigningCredentials(
                new SymmetricSecurityKey(Encoding.UTF8.GetBytes("test-signing-key-at-least-32-bytes-long!")),
                SecurityAlgorithms.HmacSha256Signature)
        };
        var handler = new JwtSecurityTokenHandler();
        var token = handler.CreateToken(tokenDescriptor);
        return handler.WriteToken(token);
    }

    [Fact]
    public async Task GetValidTokenAsync_WhenTokenUnexpired_ReusesTokenWithoutRefresh()
    {
        var secureStorageMock = new Mock<ISecureStorage>();
        var validToken = CreateJwt(DateTime.UtcNow.AddMinutes(10));
        secureStorageMock.Setup(s => s.GetSecureAsync("AccessToken")).ReturnsAsync(validToken);

        var authApiMock = new Mock<IAuthenticationApi>();
        var sessionManagerMock = new Mock<ISessionManager>();

        var tokenProvider = new TokenProvider(
            secureStorageMock.Object,
            authApiMock.Object,
            sessionManagerMock.Object,
            new NullLogger<TokenProvider>());

        var result = await tokenProvider.GetValidTokenAsync();

        Assert.Equal(validToken, result);
        authApiMock.Verify(a => a.RefreshAsync(It.IsAny<RefreshRequest>(), It.IsAny<CancellationToken>()), Times.Never);
    }

    [Fact]
    public async Task GetValidTokenAsync_WhenTokenExpired_RefreshesTokenAndPersistsReplacement()
    {
        var secureStorageMock = new Mock<ISecureStorage>();
        var expiredToken = CreateJwt(DateTime.UtcNow.AddMinutes(-5));
        secureStorageMock.Setup(s => s.GetSecureAsync("AccessToken")).ReturnsAsync(expiredToken);
        secureStorageMock.Setup(s => s.GetSecureAsync("RefreshToken")).ReturnsAsync("old_refresh_123");

        var freshAccessToken = CreateJwt(DateTime.UtcNow.AddMinutes(15));
        var authApiMock = new Mock<IAuthenticationApi>();
        authApiMock.Setup(a => a.RefreshAsync(It.Is<RefreshRequest>(r => r.RefreshToken == "old_refresh_123"), It.IsAny<CancellationToken>()))
            .ReturnsAsync(Result<LoginResponse, AuthenticationError>.Success(new LoginResponse
            {
                AccessToken = freshAccessToken,
                RefreshToken = "new_rotated_refresh_456"
            }));

        var sessionManagerMock = new Mock<ISessionManager>();

        var tokenProvider = new TokenProvider(
            secureStorageMock.Object,
            authApiMock.Object,
            sessionManagerMock.Object,
            new NullLogger<TokenProvider>());

        var result = await tokenProvider.GetValidTokenAsync();

        Assert.Equal(freshAccessToken, result);
        secureStorageMock.Verify(s => s.SaveSecureAsync("AccessToken", freshAccessToken), Times.Once);
        secureStorageMock.Verify(s => s.SaveSecureAsync("RefreshToken", "new_rotated_refresh_456"), Times.Once);
    }

    [Fact]
    public async Task GetValidTokenAsync_ConcurrentCallsWithGatedRefresh_ShareSingleRefreshOperationAndDoNotReuseOldRefreshToken()
    {
        var secureStorageMock = new Mock<ISecureStorage>();
        var expiredToken = CreateJwt(DateTime.UtcNow.AddMinutes(-5));
        var freshAccessToken = CreateJwt(DateTime.UtcNow.AddMinutes(15));

        string? storedAccess = expiredToken;
        string? storedRefresh = "concurrent_initial_refresh_token";

        secureStorageMock.Setup(s => s.GetSecureAsync("AccessToken")).ReturnsAsync(() => storedAccess);
        secureStorageMock.Setup(s => s.GetSecureAsync("RefreshToken")).ReturnsAsync(() => storedRefresh);
        secureStorageMock.Setup(s => s.SaveSecureAsync("AccessToken", It.IsAny<string>()))
            .Callback<string, string>((_, val) => storedAccess = val)
            .Returns(Task.CompletedTask);
        secureStorageMock.Setup(s => s.SaveSecureAsync("RefreshToken", It.IsAny<string>()))
            .Callback<string, string>((_, val) => storedRefresh = val)
            .Returns(Task.CompletedTask);

        var refreshCallCount = 0;
        var requestedRefreshTokens = new ConcurrentBag<string>();
        var refreshStartedTcs = new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);
        var allowRefreshToCompleteTcs = new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);

        var authApiMock = new Mock<IAuthenticationApi>();
        authApiMock.Setup(a => a.RefreshAsync(It.IsAny<RefreshRequest>(), It.IsAny<CancellationToken>()))
            .Returns(async (RefreshRequest req, CancellationToken _) =>
            {
                requestedRefreshTokens.Add(req.RefreshToken);
                Interlocked.Increment(ref refreshCallCount);
                refreshStartedTcs.TrySetResult(true);

                // Hold this refresh request open until other concurrent callers have started and queued up
                await allowRefreshToCompleteTcs.Task;

                return Result<LoginResponse, AuthenticationError>.Success(new LoginResponse
                {
                    AccessToken = freshAccessToken,
                    RefreshToken = "rotated_new_refresh_token"
                });
            });

        var tokenProvider = new TokenProvider(
            secureStorageMock.Object,
            authApiMock.Object,
            new Mock<ISessionManager>().Object,
            new NullLogger<TokenProvider>());

        // 1. Start the first caller
        var caller1Task = Task.Run(() => tokenProvider.GetValidTokenAsync());

        // 2. Wait until caller 1 enters RefreshAsync and is held open by our TCS gate
        await refreshStartedTcs.Task;

        // 3. Start 4 additional concurrent callers while caller 1 is actively inside the refresh operation
        var otherTasks = Enumerable.Range(0, 4)
            .Select(_ => Task.Run(() => tokenProvider.GetValidTokenAsync()))
            .ToArray();

        // Give other callers a short window to reach and await _refreshLock
        await Task.Delay(50);

        // 4. Release the gate so caller 1 can complete the refresh and update storage & in-memory cache
        allowRefreshToCompleteTcs.TrySetResult(true);

        // 5. Await all callers
        var allResults = await Task.WhenAll(new[] { caller1Task }.Concat(otherTasks));

        // 6. Assertions:
        // All callers must receive the exact same fresh access token
        foreach (var token in allResults)
        {
            Assert.Equal(freshAccessToken, token);
        }

        // Exactly one refresh API call must have been made
        Assert.Equal(1, refreshCallCount);
        authApiMock.Verify(a => a.RefreshAsync(It.IsAny<RefreshRequest>(), It.IsAny<CancellationToken>()), Times.Once);

        // The only refresh token ever sent to the API was the initial one
        Assert.Single(requestedRefreshTokens);
        Assert.Equal("concurrent_initial_refresh_token", requestedRefreshTokens.First());

        // The rotated refresh token was persisted in storage
        secureStorageMock.Verify(s => s.SaveSecureAsync("RefreshToken", "rotated_new_refresh_token"), Times.Once);
        secureStorageMock.Verify(s => s.SaveSecureAsync("AccessToken", freshAccessToken), Times.Once);

        // Assert old refresh token cannot be reused: exactly one call was made with it
        authApiMock.Verify(a => a.RefreshAsync(It.Is<RefreshRequest>(r => r.RefreshToken == "concurrent_initial_refresh_token"), It.IsAny<CancellationToken>()), Times.Once);

        // Assert new rotated refresh token was never submitted to RefreshAsync (proving no subsequent caller re-refreshed)
        authApiMock.Verify(a => a.RefreshAsync(It.Is<RefreshRequest>(r => r.RefreshToken == "rotated_new_refresh_token"), It.IsAny<CancellationToken>()), Times.Never);
    }

    [Fact]
    public async Task GetValidTokenAsync_AfterSuccessfulRefresh_UpdatesInMemoryCacheSoSubsequentCallsDoNotReadStorageOrCallApi()
    {
        var secureStorageMock = new Mock<ISecureStorage>();
        var expiredToken = CreateJwt(DateTime.UtcNow.AddMinutes(-5));
        var freshAccessToken = CreateJwt(DateTime.UtcNow.AddMinutes(15));

        secureStorageMock.Setup(s => s.GetSecureAsync("AccessToken")).ReturnsAsync(expiredToken);
        secureStorageMock.Setup(s => s.GetSecureAsync("RefreshToken")).ReturnsAsync("initial_refresh_token");

        var refreshCallCount = 0;
        var authApiMock = new Mock<IAuthenticationApi>();
        authApiMock.Setup(a => a.RefreshAsync(It.Is<RefreshRequest>(r => r.RefreshToken == "initial_refresh_token"), It.IsAny<CancellationToken>()))
            .ReturnsAsync(() =>
            {
                refreshCallCount++;
                return Result<LoginResponse, AuthenticationError>.Success(new LoginResponse
                {
                    AccessToken = freshAccessToken,
                    RefreshToken = "new_rotated_refresh_token"
                });
            });

        var tokenProvider = new TokenProvider(
            secureStorageMock.Object,
            authApiMock.Object,
            new Mock<ISessionManager>().Object,
            new NullLogger<TokenProvider>());

        // Call 1: Must refresh token and update in-memory cache
        var token1 = await tokenProvider.GetValidTokenAsync();
        Assert.Equal(freshAccessToken, token1);
        Assert.Equal(1, refreshCallCount);

        // Reset storage mock so any call to GetSecureAsync will fail immediately.
        // This strictly proves that the next call is satisfied 100% from in-memory _cachedAccessToken.
        secureStorageMock.Reset();
        secureStorageMock.Setup(s => s.GetSecureAsync(It.IsAny<string>()))
            .ThrowsAsync(new InvalidOperationException("In-memory cache missed: secure storage should not be queried when token is cached in memory."));

        // Call 2: Must return in-memory cached token without hitting storage or API
        var token2 = await tokenProvider.GetValidTokenAsync();
        Assert.Equal(freshAccessToken, token2);
        Assert.Equal(1, refreshCallCount); // Still exactly 1
        authApiMock.Verify(a => a.RefreshAsync(It.IsAny<RefreshRequest>(), It.IsAny<CancellationToken>()), Times.Once);
    }

    [Theory]
    [InlineData(401, "AUTH_ERROR")]
    [InlineData(401, "DEVICE_DEACTIVATED")]
    [InlineData(401, "REPLAY_DETECTED")]
    [InlineData(401, "ACCOUNT_DISABLED")]
    public async Task GetValidTokenAsync_WhenRefreshReturnsFatalRejection_ClearsSessionAndSecureStorage(int statusCode, string code)
    {
        var secureStorageMock = new Mock<ISecureStorage>();
        var expiredToken = CreateJwt(DateTime.UtcNow.AddMinutes(-5));
        secureStorageMock.Setup(s => s.GetSecureAsync("AccessToken")).ReturnsAsync(expiredToken);
        secureStorageMock.Setup(s => s.GetSecureAsync("RefreshToken")).ReturnsAsync("bad_refresh_token");

        var authApiMock = new Mock<IAuthenticationApi>();
        authApiMock.Setup(a => a.RefreshAsync(It.IsAny<RefreshRequest>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(Result<LoginResponse, AuthenticationError>.Failure(new AuthenticationError
            {
                StatusCode = statusCode,
                Code = code,
                Message = "Session terminated"
            }));

        var sessionManagerMock = new Mock<ISessionManager>();

        var tokenProvider = new TokenProvider(
            secureStorageMock.Object,
            authApiMock.Object,
            sessionManagerMock.Object,
            new NullLogger<TokenProvider>());

        var result = await tokenProvider.GetValidTokenAsync();

        Assert.Null(result);
        secureStorageMock.Verify(s => s.DeleteSecureAsync("AccessToken"), Times.Once);
        secureStorageMock.Verify(s => s.DeleteSecureAsync("RefreshToken"), Times.Once);
        secureStorageMock.Verify(s => s.DeleteSecureAsync("account_id"), Times.Once);
        sessionManagerMock.Verify(s => s.ClearSession(), Times.Once);
    }

    [Theory]
    [InlineData(500, "INTERNAL_ERROR")]
    [InlineData(429, "RATE_LIMITED")]
    [InlineData(0, "TIMEOUT")]
    public async Task GetValidTokenAsync_WhenRefreshEncounterTransientError_PreservesStorage(int statusCode, string code)
    {
        var secureStorageMock = new Mock<ISecureStorage>();
        var expiredToken = CreateJwt(DateTime.UtcNow.AddMinutes(-5));
        secureStorageMock.Setup(s => s.GetSecureAsync("AccessToken")).ReturnsAsync(expiredToken);
        secureStorageMock.Setup(s => s.GetSecureAsync("RefreshToken")).ReturnsAsync("valid_stored_refresh");

        var authApiMock = new Mock<IAuthenticationApi>();
        authApiMock.Setup(a => a.RefreshAsync(It.IsAny<RefreshRequest>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(Result<LoginResponse, AuthenticationError>.Failure(new AuthenticationError
            {
                StatusCode = statusCode,
                Code = code,
                Message = "Temporary error"
            }));

        var sessionManagerMock = new Mock<ISessionManager>();

        var tokenProvider = new TokenProvider(
            secureStorageMock.Object,
            authApiMock.Object,
            sessionManagerMock.Object,
            new NullLogger<TokenProvider>());

        var result = await tokenProvider.GetValidTokenAsync();

        Assert.Null(result);
        // Must NOT delete stored credentials or clear session on transient errors
        secureStorageMock.Verify(s => s.DeleteSecureAsync(It.IsAny<string>()), Times.Never);
        sessionManagerMock.Verify(s => s.ClearSession(), Times.Never);
    }
}

public class AuthenticationServiceSessionRestoreTests
{
    [Fact]
    public async Task TryRestoreSessionAsync_WhenValidTokenAndAccountIdExist_RestoresSessionSuccessfully()
    {
        var tokenProviderMock = new Mock<ITokenProvider>();
        tokenProviderMock.Setup(t => t.GetValidTokenAsync(It.IsAny<CancellationToken>()))
            .ReturnsAsync("valid_jwt_token");

        var secureStorageMock = new Mock<ISecureStorage>();
        secureStorageMock.Setup(s => s.GetSecureAsync("account_id"))
            .ReturnsAsync("RT-RESTORED-1001");

        var sessionFactoryMock = new Mock<ISessionFactory>();
        var expectedSession = new OverREALITY.Shared.Domain.Session.Session { JWT = "valid_jwt_token" };
        expectedSession.User.AccountId = "RT-RESTORED-1001";
        sessionFactoryMock.Setup(f => f.Create("valid_jwt_token", "RT-RESTORED-1001"))
            .Returns(expectedSession);

        var sessionManagerMock = new Mock<ISessionManager>();

        var authService = new AuthenticationService(
            new Mock<IAuthenticationApi>().Object,
            secureStorageMock.Object,
            sessionManagerMock.Object,
            tokenProviderMock.Object,
            sessionFactoryMock.Object,
            new NullLogger<AuthenticationService>());

        var restored = await authService.TryRestoreSessionAsync();

        Assert.True(restored);
        sessionManagerMock.Verify(m => m.UpdateSession(expectedSession), Times.Once);
    }

    [Fact]
    public async Task TryRestoreSessionAsync_WhenAccountIdMissingInStorage_ExtractsAccountFromJwtClaim()
    {
        var tokenDescriptor = new SecurityTokenDescriptor
        {
            Subject = new ClaimsIdentity(new[]
            {
                new Claim("account", "RT-EXTRACTED-9999")
            }),
            Expires = DateTime.UtcNow.AddMinutes(15),
            SigningCredentials = new SigningCredentials(
                new SymmetricSecurityKey(Encoding.UTF8.GetBytes("test-signing-key-at-least-32-bytes-long!")),
                SecurityAlgorithms.HmacSha256Signature)
        };
        var handler = new JwtSecurityTokenHandler();
        var tokenWithClaim = handler.WriteToken(handler.CreateToken(tokenDescriptor));

        var tokenProviderMock = new Mock<ITokenProvider>();
        tokenProviderMock.Setup(t => t.GetValidTokenAsync(It.IsAny<CancellationToken>()))
            .ReturnsAsync(tokenWithClaim);

        var secureStorageMock = new Mock<ISecureStorage>();
        secureStorageMock.Setup(s => s.GetSecureAsync("account_id"))
            .ReturnsAsync((string?)null);

        var sessionFactoryMock = new Mock<ISessionFactory>();
        var expectedSession = new OverREALITY.Shared.Domain.Session.Session { JWT = tokenWithClaim };
        sessionFactoryMock.Setup(f => f.Create(tokenWithClaim, "RT-EXTRACTED-9999"))
            .Returns(expectedSession);

        var sessionManagerMock = new Mock<ISessionManager>();

        var authService = new AuthenticationService(
            new Mock<IAuthenticationApi>().Object,
            secureStorageMock.Object,
            sessionManagerMock.Object,
            tokenProviderMock.Object,
            sessionFactoryMock.Object,
            new NullLogger<AuthenticationService>());

        var restored = await authService.TryRestoreSessionAsync();

        Assert.True(restored);
        sessionManagerMock.Verify(m => m.UpdateSession(expectedSession), Times.Once);
        secureStorageMock.Verify(s => s.SaveSecureAsync("account_id", "RT-EXTRACTED-9999"), Times.Once);
    }

    [Fact]
    public async Task TryRestoreSessionAsync_WhenTokenProviderReturnsNull_ReturnsFalse()
    {
        var tokenProviderMock = new Mock<ITokenProvider>();
        tokenProviderMock.Setup(t => t.GetValidTokenAsync(It.IsAny<CancellationToken>()))
            .ReturnsAsync((string?)null);

        var sessionManagerMock = new Mock<ISessionManager>();

        var authService = new AuthenticationService(
            new Mock<IAuthenticationApi>().Object,
            new Mock<ISecureStorage>().Object,
            sessionManagerMock.Object,
            tokenProviderMock.Object,
            new Mock<ISessionFactory>().Object,
            new NullLogger<AuthenticationService>());

        var restored = await authService.TryRestoreSessionAsync();

        Assert.False(restored);
        sessionManagerMock.Verify(m => m.UpdateSession(It.IsAny<OverREALITY.Shared.Domain.Session.Session>()), Times.Never);
    }
}
