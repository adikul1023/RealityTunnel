using System;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging.Abstractions;
using Moq;
using OverREALITY.Core.Services;
using OverREALITY.Shared.Api.Authentication;
using OverREALITY.Shared.Errors;
using OverREALITY.Shared.Interfaces;
using OverREALITY.Shared.Domain.Session;
using Xunit;

namespace OverREALITY.Tests.Core;

public class AuthenticationTests
{
    [Fact]
    public async Task LoginAsync_SuccessfulLogin_ReturnsTokensAndUpdatesSession()
    {
        var authApiMock = new Mock<IAuthenticationApi>();
        var loginResponse = new LoginResponse { AccessToken = "test_access", RefreshToken = "test_refresh" };
        authApiMock.Setup(a => a.LoginAsync(It.IsAny<LoginRequest>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(Result<LoginResponse, AuthenticationError>.Success(loginResponse));

        var secureStorageMock = new Mock<ISecureStorage>();
        var sessionManagerMock = new Mock<ISessionManager>();
        var tokenProviderMock = new Mock<ITokenProvider>();
        var sessionFactoryMock = new Mock<ISessionFactory>();
        
        var expectedSession = new Session { JWT = "test_access" };
        sessionFactoryMock.Setup(s => s.Create("test_access", "ST-TEST-1234")).Returns(expectedSession);

        var authService = new AuthenticationService(
            authApiMock.Object, 
            secureStorageMock.Object, 
            sessionManagerMock.Object, 
            tokenProviderMock.Object, 
            sessionFactoryMock.Object, 
            new NullLogger<AuthenticationService>()
        );

        var result = await authService.LoginAsync("ST-TEST-1234", "abcdef123456");

        Assert.True(result.IsSuccess);
        Assert.NotNull(result.Value);
        Assert.Equal("test_access", result.Value.AccessToken);

        secureStorageMock.Verify(s => s.SaveSecureAsync("AccessToken", "test_access"), Times.Once);
        secureStorageMock.Verify(s => s.SaveSecureAsync("RefreshToken", "test_refresh"), Times.Once);
        sessionManagerMock.Verify(s => s.UpdateSession(expectedSession), Times.Once);
    }

    [Fact]
    public async Task LoginAsync_ApiFails_ReturnsError()
    {
        var authApiMock = new Mock<IAuthenticationApi>();
        authApiMock.Setup(a => a.LoginAsync(It.IsAny<LoginRequest>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(Result<LoginResponse, AuthenticationError>.Failure(new AuthenticationError { Message = "Unauthorized access.", Code = "401" }));

        var authService = new AuthenticationService(
            authApiMock.Object, 
            new Mock<ISecureStorage>().Object, 
            new Mock<ISessionManager>().Object, 
            new Mock<ITokenProvider>().Object, 
            new Mock<ISessionFactory>().Object, 
            new NullLogger<AuthenticationService>()
        );

        var result = await authService.LoginAsync("ST-TEST-1234", "wrong_token");

        Assert.False(result.IsSuccess);
        Assert.NotNull(result.Error);
        Assert.Equal("Unauthorized access.", result.Error.Message);
        Assert.Equal("401", result.Error.Code);
    }

    [Fact]
    public async Task LoginAsync_BackendRequires2Fa_PropagatesRequires2FaError()
    {
        var authApiMock = new Mock<IAuthenticationApi>();
        authApiMock.Setup(a => a.LoginAsync(It.Is<LoginRequest>(r => r.TwoFaCode == null), It.IsAny<CancellationToken>()))
            .ReturnsAsync(Result<LoginResponse, AuthenticationError>.Failure(new AuthenticationError 
            { 
                Message = "Two-factor authentication required", 
                Code = "REQUIRES_2FA", 
                StatusCode = 401, 
                Requires2Fa = true 
            }));

        var authService = new AuthenticationService(
            authApiMock.Object, 
            new Mock<ISecureStorage>().Object, 
            new Mock<ISessionManager>().Object, 
            new Mock<ITokenProvider>().Object, 
            new Mock<ISessionFactory>().Object, 
            new NullLogger<AuthenticationService>()
        );

        var result = await authService.LoginAsync("ST-TEST-1234", "abcdef123456");

        Assert.False(result.IsSuccess);
        Assert.NotNull(result.Error);
        Assert.True(result.Error.Requires2Fa);
        Assert.Equal("REQUIRES_2FA", result.Error.Code);
        Assert.Equal(401, result.Error.StatusCode);
    }

    [Fact]
    public async Task LoginAsync_WithValidOtp_SubmitsTwoFaCodeAndSucceeds()
    {
        var authApiMock = new Mock<IAuthenticationApi>();
        var loginResponse = new LoginResponse { AccessToken = "valid_access_token", RefreshToken = "valid_refresh_token" };
        
        LoginRequest? capturedRequest = null;
        authApiMock.Setup(a => a.LoginAsync(It.IsAny<LoginRequest>(), It.IsAny<CancellationToken>()))
            .Callback<LoginRequest, CancellationToken>((req, _) => capturedRequest = req)
            .ReturnsAsync(Result<LoginResponse, AuthenticationError>.Success(loginResponse));

        var secureStorageMock = new Mock<ISecureStorage>();
        var sessionManagerMock = new Mock<ISessionManager>();
        var sessionFactoryMock = new Mock<ISessionFactory>();
        sessionFactoryMock.Setup(s => s.Create("valid_access_token", "ST-TEST-1234")).Returns(new Session { JWT = "valid_access_token" });

        var authService = new AuthenticationService(
            authApiMock.Object, 
            secureStorageMock.Object, 
            sessionManagerMock.Object, 
            new Mock<ITokenProvider>().Object, 
            sessionFactoryMock.Object, 
            new NullLogger<AuthenticationService>()
        );

        var result = await authService.LoginAsync("ST-TEST-1234", "abcdef123456", "123456");

        Assert.True(result.IsSuccess);
        Assert.NotNull(capturedRequest);
        Assert.Equal("123456", capturedRequest.TwoFaCode);
        Assert.Equal("ST-TEST-1234", capturedRequest.AccountId);
        Assert.Equal("abcdef123456", capturedRequest.MasterToken);
        secureStorageMock.Verify(s => s.SaveSecureAsync("AccessToken", "valid_access_token"), Times.Once);
    }

    [Fact]
    public async Task LoginAsync_WithBackupCode_SubmitsBackupCodeAndSucceeds()
    {
        var authApiMock = new Mock<IAuthenticationApi>();
        var loginResponse = new LoginResponse { AccessToken = "valid_backup_access", RefreshToken = "valid_backup_refresh" };
        
        LoginRequest? capturedRequest = null;
        authApiMock.Setup(a => a.LoginAsync(It.IsAny<LoginRequest>(), It.IsAny<CancellationToken>()))
            .Callback<LoginRequest, CancellationToken>((req, _) => capturedRequest = req)
            .ReturnsAsync(Result<LoginResponse, AuthenticationError>.Success(loginResponse));

        var secureStorageMock = new Mock<ISecureStorage>();
        var sessionManagerMock = new Mock<ISessionManager>();
        var sessionFactoryMock = new Mock<ISessionFactory>();
        sessionFactoryMock.Setup(s => s.Create("valid_backup_access", "ST-TEST-1234")).Returns(new Session { JWT = "valid_backup_access" });

        var authService = new AuthenticationService(
            authApiMock.Object, 
            secureStorageMock.Object, 
            sessionManagerMock.Object, 
            new Mock<ITokenProvider>().Object, 
            sessionFactoryMock.Object, 
            new NullLogger<AuthenticationService>()
        );

        var result = await authService.LoginAsync("ST-TEST-1234", "abcdef123456", "backup-code-87654321");

        Assert.True(result.IsSuccess);
        Assert.NotNull(capturedRequest);
        Assert.Equal("backup-code-87654321", capturedRequest.TwoFaCode);
        secureStorageMock.Verify(s => s.SaveSecureAsync("AccessToken", "valid_backup_access"), Times.Once);
    }

    [Fact]
    public async Task LoginAsync_WithInvalidOtp_ReturnsFailureWithoutTokens()
    {
        var authApiMock = new Mock<IAuthenticationApi>();
        authApiMock.Setup(a => a.LoginAsync(It.Is<LoginRequest>(r => r.TwoFaCode == "000000"), It.IsAny<CancellationToken>()))
            .ReturnsAsync(Result<LoginResponse, AuthenticationError>.Failure(new AuthenticationError 
            { 
                Message = "Authentication failed: invalid two-factor authentication code", 
                Code = "Unauthorized", 
                StatusCode = 401,
                Requires2Fa = false
            }));

        var secureStorageMock = new Mock<ISecureStorage>();
        var sessionManagerMock = new Mock<ISessionManager>();

        var authService = new AuthenticationService(
            authApiMock.Object, 
            secureStorageMock.Object, 
            sessionManagerMock.Object, 
            new Mock<ITokenProvider>().Object, 
            new Mock<ISessionFactory>().Object, 
            new NullLogger<AuthenticationService>()
        );

        var result = await authService.LoginAsync("ST-TEST-1234", "abcdef123456", "000000");

        Assert.False(result.IsSuccess);
        Assert.NotNull(result.Error);
        Assert.Equal("Authentication failed: invalid two-factor authentication code", result.Error.Message);
        Assert.False(result.Error.Requires2Fa);
        secureStorageMock.Verify(s => s.SaveSecureAsync("AccessToken", It.IsAny<string>()), Times.Never);
    }

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
        var expectedSession = new Session { JWT = "valid_jwt_token" };
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
        // Construct a JWT with an account claim
        var tokenDescriptor = new Microsoft.IdentityModel.Tokens.SecurityTokenDescriptor
        {
            Subject = new System.Security.Claims.ClaimsIdentity(new[]
            {
                new System.Security.Claims.Claim("account", "RT-EXTRACTED-9999")
            }),
            Expires = DateTime.UtcNow.AddMinutes(15),
            SigningCredentials = new Microsoft.IdentityModel.Tokens.SigningCredentials(
                new Microsoft.IdentityModel.Tokens.SymmetricSecurityKey(System.Text.Encoding.UTF8.GetBytes("test-signing-key-at-least-32-bytes-long!")),
                Microsoft.IdentityModel.Tokens.SecurityAlgorithms.HmacSha256Signature)
        };
        var handler = new System.IdentityModel.Tokens.Jwt.JwtSecurityTokenHandler();
        var tokenWithClaim = handler.WriteToken(handler.CreateToken(tokenDescriptor));

        var tokenProviderMock = new Mock<ITokenProvider>();
        tokenProviderMock.Setup(t => t.GetValidTokenAsync(It.IsAny<CancellationToken>()))
            .ReturnsAsync(tokenWithClaim);

        var secureStorageMock = new Mock<ISecureStorage>();
        secureStorageMock.Setup(s => s.GetSecureAsync("account_id"))
            .ReturnsAsync((string?)null);

        var sessionFactoryMock = new Mock<ISessionFactory>();
        var expectedSession = new Session { JWT = tokenWithClaim };
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
        sessionManagerMock.Verify(m => m.UpdateSession(It.IsAny<Session>()), Times.Never);
    }

    [Fact]
    public async Task LogoutAsync_ClearsSecureStorageAndSession()
    {
        var secureStorageMock = new Mock<ISecureStorage>();
        var tokenProviderMock = new Mock<ITokenProvider>();
        var sessionManagerMock = new Mock<ISessionManager>();

        var authService = new AuthenticationService(
            new Mock<IAuthenticationApi>().Object,
            secureStorageMock.Object,
            sessionManagerMock.Object,
            tokenProviderMock.Object,
            new Mock<ISessionFactory>().Object,
            new NullLogger<AuthenticationService>());

        var result = await authService.LogoutAsync();

        Assert.True(result.IsSuccess);
        secureStorageMock.Verify(s => s.DeleteSecureAsync("AccessToken"), Times.Once);
        secureStorageMock.Verify(s => s.DeleteSecureAsync("RefreshToken"), Times.Once);
        secureStorageMock.Verify(s => s.DeleteSecureAsync("account_id"), Times.Once);
        tokenProviderMock.Verify(t => t.InvalidateToken(), Times.Once);
        sessionManagerMock.Verify(m => m.ClearSession(), Times.Once);
    }
}

