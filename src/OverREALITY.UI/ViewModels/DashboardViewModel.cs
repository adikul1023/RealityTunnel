using System;
using System.Threading.Tasks;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using OverREALITY.Shared.Api;
using OverREALITY.Shared.Interfaces;
using OverREALITY.UI.Services;
using OverREALITY.UI.Models;

namespace OverREALITY.UI.ViewModels;

public partial class DashboardViewModel : ObservableObject, IDisposable
{
    private readonly IConnectionService _connectionService;
    private readonly IConnectionStateManager _stateManager;

    [ObservableProperty]
    private ConnectionPresentationState _presentationState = new();

    [ObservableProperty]
    private int _selectedServerIndex = 0;

    private readonly IUiDispatcher _dispatcher;
    public DashboardViewModel(IConnectionService connectionService, IConnectionStateManager stateManager, IUiDispatcher dispatcher)
    {
        _connectionService = connectionService;
        _stateManager = stateManager;
        _dispatcher = dispatcher;

        _stateManager.StateChanged += OnStateChanged;
        UpdatePresentationState(_stateManager.CurrentState);
    }

    private void OnStateChanged(object? sender, ConnectionState e)
    {
        _dispatcher.Invoke(() => UpdatePresentationState(e));
    }

    private void UpdatePresentationState(ConnectionState state)
    {
        PresentationState = state switch
        {
            ConnectionState.Disconnected => new ConnectionPresentationState
            {
                Title = "Disconnected",
                Subtitle = "Ready to connect",
                IsBusy = false,
                CanConnect = true,
                CanDisconnect = false,
                AccentColor = "Gray"
            },
            ConnectionState.Authenticating => new ConnectionPresentationState
            {
                Title = "Connecting...",
                Subtitle = "Authenticating with server",
                IsBusy = true,
                CanConnect = false,
                CanDisconnect = true,
                AccentColor = "Orange"
            },
            ConnectionState.Provisioning => new ConnectionPresentationState
            {
                Title = "Connecting...",
                Subtitle = "Provisioning secure tunnel",
                IsBusy = true,
                CanConnect = false,
                CanDisconnect = true,
                AccentColor = "Orange"
            },
            ConnectionState.StartingHelper => new ConnectionPresentationState
            {
                Title = "Connecting...",
                Subtitle = "Starting VPN runtime",
                IsBusy = true,
                CanConnect = false,
                CanDisconnect = true,
                AccentColor = "Orange"
            },
            ConnectionState.Connecting => new ConnectionPresentationState
            {
                Title = "Connecting...",
                Subtitle = "Establishing connection",
                IsBusy = true,
                CanConnect = false,
                CanDisconnect = true,
                AccentColor = "Orange"
            },
            ConnectionState.Connected => new ConnectionPresentationState
            {
                Title = "Connected",
                Subtitle = "Your connection is secure",
                IsBusy = false,
                CanConnect = false,
                CanDisconnect = true,
                AccentColor = "Lime"
            },
            ConnectionState.Reconnecting => new ConnectionPresentationState
            {
                Title = "Reconnecting...",
                Subtitle = "Restoring connection",
                IsBusy = true,
                CanConnect = false,
                CanDisconnect = true,
                AccentColor = "Orange"
            },
            ConnectionState.Disconnecting => new ConnectionPresentationState
            {
                Title = "Disconnecting...",
                Subtitle = "Closing tunnel",
                IsBusy = true,
                CanConnect = false,
                CanDisconnect = false,
                AccentColor = "Orange"
            },
            ConnectionState.Failed => new ConnectionPresentationState
            {
                Title = "Connection Failed",
                Subtitle = _stateManager.LastError ?? "An error occurred",
                IsBusy = false,
                CanConnect = true,
                CanDisconnect = false,
                AccentColor = "Red"
            },
            _ => PresentationState
        };

        ConnectCommand.NotifyCanExecuteChanged();
        DisconnectCommand.NotifyCanExecuteChanged();
    }

    [RelayCommand(CanExecute = nameof(CanConnect))]
    private async Task ConnectAsync()
    {
        await _connectionService.ConnectAsync(SelectedServerIndex);
    }

    private bool CanConnect() => PresentationState.CanConnect;

    [RelayCommand(CanExecute = nameof(CanDisconnect))]
    private async Task DisconnectAsync()
    {
        await _connectionService.DisconnectAsync();
    }

    private bool CanDisconnect() => PresentationState.CanDisconnect;

    public void Dispose()
    {
        _stateManager.StateChanged -= OnStateChanged;
    }
}
