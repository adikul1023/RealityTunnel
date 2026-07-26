using System;
using OverREALITY.Shared.Api;

namespace OverREALITY.Shared.Interfaces;

public interface IConnectionStateManager
{
    ConnectionState CurrentState { get; }
    string? LastError { get; }
    event EventHandler<ConnectionState> StateChanged;
    
    void SetState(ConnectionState state, string? error = null);
}
