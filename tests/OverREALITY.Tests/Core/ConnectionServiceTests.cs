using OverREALITY.Shared.Api;

using Microsoft.Extensions.Logging;
using System;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging.Abstractions;
using Moq;
using OverREALITY.Core.Services;
using OverREALITY.Shared.Api.Configuration;
using OverREALITY.Shared.Api.VpnRuntime;
using OverREALITY.Shared.Errors;
using OverREALITY.Shared.Interfaces;
using Xunit;

namespace OverREALITY.Tests.Core;

public class ConnectionServiceTests
{
    private Mock<IConnectionStateManager> mockStateManager;
    private Mock<IConnectionProvisioningService> mockProvisioning;
    private Mock<IHelperClient> mockHelperClient;
    private Mock<IOperationContext> mockContext;
    private Mock<ILogger<ConnectionService>> mockLogger;
    private Mock<IAuthService> mockAuthService;

    public ConnectionServiceTests()
    {
        mockStateManager = new Mock<IConnectionStateManager>();
        mockProvisioning = new Mock<IConnectionProvisioningService>();
        mockHelperClient = new Mock<IHelperClient>();
        mockContext = new Mock<IOperationContext>();
        mockLogger = new Mock<ILogger<ConnectionService>>();
        mockAuthService = new Mock<IAuthService>();

        var mockScope = new Mock<IDisposable>();
        mockContext.Setup(x => x.BeginOperation(It.IsAny<string>())).Returns(mockScope.Object);
    }

    [Fact]
    public async Task ConnectAsync_SuccessfulSequence_TransitionsToConnected()
    {
        var config = new VPNConfig();
        mockProvisioning.Setup(x => x.ConnectProvisionAsync(It.IsAny<CancellationToken>()))
            .ReturnsAsync(Result<VPNConfig, ProvisioningError>.Success(config));
            
        mockHelperClient.Setup(x => x.StartAsync(It.IsAny<StartVpnRequest>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(Result<bool, HelperError>.Success(true));

        var connectionService = new ConnectionService(
            mockStateManager.Object,
            mockProvisioning.Object,
            mockHelperClient.Object,
            mockContext.Object,
            mockAuthService.Object,
            mockLogger.Object);

        await connectionService.ConnectAsync();

        mockStateManager.Verify(x => x.SetState(ConnectionState.Provisioning, It.IsAny<string?>()), Times.Once);
        mockStateManager.Verify(x => x.SetState(ConnectionState.StartingHelper, It.IsAny<string?>()), Times.Once);
        mockStateManager.Verify(x => x.SetState(ConnectionState.Connected, It.IsAny<string?>()), Times.Once);
    }
}
