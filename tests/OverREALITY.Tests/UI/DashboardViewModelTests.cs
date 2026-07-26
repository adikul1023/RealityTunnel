using Moq;
using OverREALITY.Shared.Api;
using OverREALITY.Shared.Interfaces;
using OverREALITY.UI.Services;
using OverREALITY.UI.Models;
using OverREALITY.UI.ViewModels;
using Xunit;

namespace OverREALITY.Tests.UI;

public class DashboardViewModelTests
{
    [Fact]
    public void Constructor_InitializesStateFromStateManager()
    {
        var connectionServiceMock = new Mock<IConnectionService>();
        var stateManagerMock = new Mock<IConnectionStateManager>();

        stateManagerMock.Setup(m => m.CurrentState).Returns(ConnectionState.Authenticating);

        var dispatcherMock = new Mock<IUiDispatcher>();
        dispatcherMock.Setup(d => d.Invoke(It.IsAny<System.Action>())).Callback<System.Action>(a => a());

        var viewModel = new DashboardViewModel(connectionServiceMock.Object, stateManagerMock.Object, dispatcherMock.Object);

        Assert.Equal("Connecting...", viewModel.PresentationState.Title);
        Assert.True(viewModel.PresentationState.IsBusy);
        Assert.False(viewModel.PresentationState.CanConnect);
    }
}
