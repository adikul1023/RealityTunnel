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
}
