using System;
using Microsoft.Extensions.Logging;
using OverREALITY.Shared.Api.VpnRuntime;

namespace OverREALITY.Helper;

public class HelperStateMachine
{
    private readonly object _lock = new();
    private HelperStatus _status = HelperStatus.Stopped;
    private readonly ILogger<HelperStateMachine> _logger;

    public HelperStateMachine(ILogger<HelperStateMachine> logger)
    {
        _logger = logger;
    }

    public HelperStatus CurrentStatus
    {
        get
        {
            lock (_lock)
            {
                return _status;
            }
        }
    }

    public void TransitionTo(HelperStatus newStatus)
    {
        lock (_lock)
        {
            if (!IsValidTransition(_status, newStatus))
            {
                throw new InvalidOperationException($"Invalid state transition from {_status} to {newStatus}.");
            }

            _logger.LogInformation("Transitioning helper state: {OldStatus} -> {NewStatus}", _status, newStatus);
            _status = newStatus;
        }
    }

    private bool IsValidTransition(HelperStatus current, HelperStatus next)
    {
        return (current, next) switch
        {
            (HelperStatus.Stopped, HelperStatus.Starting) => true,
            (HelperStatus.Starting, HelperStatus.Running) => true,
            (HelperStatus.Starting, HelperStatus.Stopped) => true, // Failed to start
            (HelperStatus.Starting, HelperStatus.Crashed) => true, // Process crashed immediately during start
            (HelperStatus.Running, HelperStatus.Stopping) => true,
            (HelperStatus.Stopping, HelperStatus.Stopped) => true,
            (HelperStatus.Running, HelperStatus.Crashed) => true,
            (HelperStatus.Crashed, HelperStatus.Restarting) => true,
            (HelperStatus.Crashed, HelperStatus.Stopped) => true, // Given up restarting before transitioning to Restarting
            (HelperStatus.Restarting, HelperStatus.Starting) => true,
            (HelperStatus.Restarting, HelperStatus.Stopped) => true, // Give up restarting
            _ => false
        };
    }
}
