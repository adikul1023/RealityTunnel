using System;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Logging.Abstractions;
using Moq;
using OverREALITY.Core.Services;
using OverREALITY.Shared.Api;
using OverREALITY.Shared.Api.Authentication;
using OverREALITY.Shared.Api.Configuration;
using OverREALITY.Shared.Api.VpnRuntime;
using OverREALITY.Shared.Domain.Session;
using OverREALITY.Shared.Errors;
using OverREALITY.Shared.Interfaces;
using Xunit;

namespace OverREALITY.Tests.Integration;

public class ConnectionWorkflowTests
{
    private readonly Mock<IConnectionProvisioningService> _mockProvisioning;
    private readonly Mock<IHelperClient> _mockHelperClient;
    private readonly Mock<IOperationContext> _mockOperationContext;
    private readonly Mock<ILogger<ConnectionService>> _mockLogger;
    private readonly Mock<IAuthService> _mockAuthService;
    private readonly IConnectionStateManager _stateManager;
    private readonly ConnectionService _connectionService;

    public ConnectionWorkflowTests()
    {
        _mockProvisioning = new Mock<IConnectionProvisioningService>();
        _mockHelperClient = new Mock<IHelperClient>();
        _mockOperationContext = new Mock<IOperationContext>();
        _mockLogger = new Mock<ILogger<ConnectionService>>();
        _mockAuthService = new Mock<IAuthService>();
        _stateManager = new ConnectionStateManager();

        var mockScope = new Mock<IDisposable>();
        _mockOperationContext.Setup(x => x.BeginOperation(It.IsAny<string>())).Returns(mockScope.Object);

        _connectionService = new ConnectionService(
            _stateManager,
            _mockProvisioning.Object,
            _mockHelperClient.Object,
            _mockOperationContext.Object,
            _mockAuthService.Object,
            _mockLogger.Object
        );
    }

    [Fact]
    public async Task Connect_WhenProvisioningFails_TransitionsToFailedWithRichError()
    {

        _mockProvisioning.Setup(x => x.ConnectProvisionAsync(It.IsAny<CancellationToken>()))
            .ReturnsAsync(Result<VPNConfig, ProvisioningError>.Failure(new ProvisioningError { Code = "PROV_ERR", Message = "Out of nodes" }));

        await _connectionService.ConnectAsync();

        Assert.Equal(ConnectionState.Failed, _stateManager.CurrentState);
        Assert.Contains("Out of nodes", _stateManager.LastError);
    }

    [Fact]
    public async Task Connect_WhenHelperFails_TransitionsToFailedWithRichError()
    {
        _mockProvisioning.Setup(x => x.ConnectProvisionAsync(It.IsAny<CancellationToken>()))
            .ReturnsAsync(Result<VPNConfig, ProvisioningError>.Success(new VPNConfig()));

        _mockHelperClient.Setup(x => x.StartAsync(It.IsAny<StartVpnRequest>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(Result<bool, HelperError>.Failure(new HelperError { Code = "START_ERR", Message = "Port in use" }));

        await _connectionService.ConnectAsync();

        Assert.Equal(ConnectionState.Failed, _stateManager.CurrentState);
        Assert.Contains("Port in use", _stateManager.LastError);
    }

    [Fact]
    public async Task ConnectAndDisconnect_SuccessfulWorkflow_TransitionsCorrectly()
    {
        _mockProvisioning.Setup(x => x.ConnectProvisionAsync(It.IsAny<CancellationToken>()))
            .ReturnsAsync(Result<VPNConfig, ProvisioningError>.Success(new VPNConfig()));

        _mockHelperClient.Setup(x => x.StartAsync(It.IsAny<StartVpnRequest>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(Result<bool, HelperError>.Success(true));
            
        _mockHelperClient.Setup(x => x.StopAsync(It.IsAny<CancellationToken>()))
            .ReturnsAsync(Result<bool, HelperError>.Success(true));

        await _connectionService.ConnectAsync();
        Assert.Equal(ConnectionState.Connected, _stateManager.CurrentState);
        
        await _connectionService.DisconnectAsync();
        Assert.Equal(ConnectionState.Disconnected, _stateManager.CurrentState);
    }
}
