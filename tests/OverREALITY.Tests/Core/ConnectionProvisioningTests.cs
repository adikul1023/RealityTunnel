using System.Threading.Tasks;
using Microsoft.Extensions.Logging.Abstractions;
using Moq;
using OverREALITY.Core.Services;
using OverREALITY.Shared.Api.Configuration;
using OverREALITY.Shared.Errors;
using System.Threading;
using OverREALITY.Shared.Interfaces;
using Xunit;

namespace OverREALITY.Tests.Core;

public class ConnectionProvisioningTests
{
    [Fact]
    public async Task ConnectProvisionAsync_ValidProfile_ReturnsConfig()
    {
        var apiClientMock = new Mock<IApiClient>();
        var validProfile = new ServerProfileDto { Server = "test.server.com", Port = 443, Uuid = "uuid-123", Transport = "vless" };
        apiClientMock.Setup(a => a.GetAsync<ServerProfileDto>("/api/provision/profile", It.IsAny<CancellationToken>()))
            .ReturnsAsync(Result<ServerProfileDto, ApiError>.Success(validProfile));

        var configBuilderMock = new Mock<IConfigurationBuilder>();
        configBuilderMock.Setup(c => c.Build(validProfile)).Returns(new VPNConfig { JsonConfig = "{}" });

        var validatorMock = new Mock<IServerProfileValidator>();
        validatorMock.Setup(v => v.Validate(validProfile)).Returns(Result<bool, ProvisioningError>.Success(true));
        var service = new ConnectionProvisioningService(apiClientMock.Object, configBuilderMock.Object, validatorMock.Object, new NullLogger<ConnectionProvisioningService>());

        var result = await service.ConnectProvisionAsync();

        Assert.True(result.IsSuccess);
        Assert.NotNull(result.Value);
        Assert.Equal("{}", result.Value.JsonConfig);
    }

    [Fact]
    public async Task ConnectProvisionAsync_InvalidProfile_ReturnsError()
    {
        var apiClientMock = new Mock<IApiClient>();
        var invalidProfile = new ServerProfileDto { Server = "", Port = 0 };
        apiClientMock.Setup(a => a.GetAsync<ServerProfileDto>("/api/provision/profile", It.IsAny<CancellationToken>()))
            .ReturnsAsync(Result<ServerProfileDto, ApiError>.Success(invalidProfile));

        var validatorMock = new Mock<IServerProfileValidator>();
        validatorMock.Setup(v => v.Validate(invalidProfile)).Returns(Result<bool, ProvisioningError>.Failure(new ProvisioningError { Code = "INVALID_PROFILE" }));
        var service = new ConnectionProvisioningService(apiClientMock.Object, new Mock<IConfigurationBuilder>().Object, validatorMock.Object, new NullLogger<ConnectionProvisioningService>());

        var result = await service.ConnectProvisionAsync();

        Assert.False(result.IsSuccess);
        Assert.NotNull(result.Error);
        Assert.Equal("INVALID_PROFILE", result.Error.Code);
    }
}
