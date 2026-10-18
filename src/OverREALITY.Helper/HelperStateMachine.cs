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

    public bool TryTransitionTo(HelperStatus newStatus, out HelperStatus previousStatus)
    {
        lock (_lock)
        {
            previousStatus = _status;

            if (_status == newStatus)
            {
                return true;
            }

            if (!IsValidTransition(_status, newStatus))
            {
                _logger.LogWarning("Invalid state transition attempted: {OldStatus} -> {NewStatus}", _status, newStatus);
                return false;
            }

            _logger.LogInformation("Transitioning helper state: {OldStatus} -> {NewStatus}", _status, newStatus);
            _status = newStatus;
            return true;
        }
    }

    public void TransitionTo(HelperStatus newStatus)
    {
        if (!TryTransitionTo(newStatus, out var previousStatus))
        {
            throw new InvalidOperationException($"Invalid state transition from {previousStatus} to {newStatus}.");
        }
    }

    private bool IsValidTransition(HelperStatus current, HelperStatus next)
    {
        return (current, next) switch
        {
            (HelperStatus.Stopped, HelperStatus.Starting) => true,
            (HelperStatus.Starting, HelperStatus.Running) => true,
            (HelperStatus.Starting, HelperStatus.Stopped) => true,
            (HelperStatus.Running, HelperStatus.Stopping) => true,
            (HelperStatus.Stopping, HelperStatus.Stopped) => true,
            (HelperStatus.Running, HelperStatus.Crashed) => true,
            (HelperStatus.Crashed, HelperStatus.Restarting) => true,
            (HelperStatus.Crashed, HelperStatus.Stopped) => true,
            (HelperStatus.Restarting, HelperStatus.Starting) => true,
            (HelperStatus.Restarting, HelperStatus.Stopped) => true,
            _ => false
        };
    }
}
