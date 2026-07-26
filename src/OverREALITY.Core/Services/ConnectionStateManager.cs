using System;
using OverREALITY.Shared.Api;
using OverREALITY.Shared.Interfaces;

namespace OverREALITY.Core.Services;

public class ConnectionStateManager : IConnectionStateManager
{
    public ConnectionState CurrentState { get; private set; } = ConnectionState.Disconnected;
    public string? LastError { get; private set; }

    public event EventHandler<ConnectionState>? StateChanged;

    public void SetState(ConnectionState state, string? error = null)
    {
        if (CurrentState != state || error != LastError)
        {
            CurrentState = state;
            LastError = error;
            StateChanged?.Invoke(this, state);
        }
    }
}
