using System;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using OverREALITY.Shared.Api.VpnRuntime;

namespace OverREALITY.Helper;

public class ProcessSupervisor : IDisposable
{
    private readonly SingboxProcessManager _processManager;
    private readonly HelperStateMachine _stateMachine;
    private readonly ILogger<ProcessSupervisor> _logger;
    private readonly object _lifecycleLock = new();
    private int _crashCount;
    private const int MaxCrashes = 3;
    private string? _lastConfig;
    private bool _isDisposed;

    public ProcessSupervisor(SingboxProcessManager processManager, HelperStateMachine stateMachine, ILogger<ProcessSupervisor> logger)
    {
        _processManager = processManager;
        _stateMachine = stateMachine;
        _logger = logger;
        
        _processManager.ProcessExited += OnProcessExited;
    }

    public async Task StartSupervisedAsync(string configJson, CancellationToken cancellationToken = default)
    {
        lock (_lifecycleLock)
        {
            var currentStatus = _stateMachine.CurrentStatus;
            if (currentStatus == HelperStatus.Running || currentStatus == HelperStatus.Starting)
            {
                throw new InvalidOperationException($"VPN is already {currentStatus}.");
            }
            _crashCount = 0;
            _lastConfig = configJson;
        }

        await StartInternalAsync(configJson, cancellationToken);
    }

    public void StopSupervised()
    {
        lock (_lifecycleLock)
        {
            var status = _stateMachine.CurrentStatus;
            if (status == HelperStatus.Running || status == HelperStatus.Restarting)
            {
                _stateMachine.TryTransitionTo(HelperStatus.Stopping, out _);
            }
        }

        try
        {
            _processManager.Stop();
        }
        finally
        {
            lock (_lifecycleLock)
            {
                _stateMachine.TryTransitionTo(HelperStatus.Stopped, out _);
            }
        }
    }

    private async Task StartInternalAsync(string configJson, CancellationToken cancellationToken)
    {
        lock (_lifecycleLock)
        {
            _stateMachine.TransitionTo(HelperStatus.Starting);
        }

        try
        {
            await _processManager.StartAsync(configJson, cancellationToken);
            lock (_lifecycleLock)
            {
                _stateMachine.TransitionTo(HelperStatus.Running);
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to start VPN process.");
            lock (_lifecycleLock)
            {
                try { _processManager.Stop(); } catch { }
                _stateMachine.TryTransitionTo(HelperStatus.Stopped, out _);
            }
            throw;
        }
    }

    private async void OnProcessExited(object? sender, ProcessExitedEventArgs e)
    {
        try
        {
            bool shouldRestart = false;
            lock (_lifecycleLock)
            {
                if (_isDisposed) return;

                var status = _stateMachine.CurrentStatus;
                // Only supervise unexpected crashes of an actively running process.
                // Startup failures are handled directly by StartInternalAsync.
                // Intentional stops are handled by StopSupervised.
                if (status != HelperStatus.Running)
                {
                    _logger.LogInformation("Process exited while helper was in state {Status} (Code: {Code}, Runtime: {Runtime}). Ignoring supervisor crash handling.", 
                        status, e.ExitCode, e.Runtime);
                    return;
                }

                _logger.LogWarning("Process exited unexpectedly while Running (Code: {Code}, Runtime: {Runtime}).", e.ExitCode, e.Runtime);
                
                if (_stateMachine.TryTransitionTo(HelperStatus.Crashed, out _))
                {
                    _crashCount++;

                    if (_crashCount > MaxCrashes)
                    {
                        _logger.LogCritical("Maximum crash count ({Max}) exceeded. Giving up.", MaxCrashes);
                        _stateMachine.TryTransitionTo(HelperStatus.Stopped, out _);
                        return;
                    }

                    _logger.LogInformation("Attempting restart {Count} of {Max}.", _crashCount, MaxCrashes);
                    if (_stateMachine.TryTransitionTo(HelperStatus.Restarting, out _))
                    {
                        shouldRestart = true;
                    }
                }
            }

            if (shouldRestart)
            {
                // Exponential backoff
                await Task.Delay(TimeSpan.FromSeconds(Math.Pow(2, _crashCount)));
                
                string? configToUse = null;
                lock (_lifecycleLock)
                {
                    if (_isDisposed || _stateMachine.CurrentStatus != HelperStatus.Restarting || _lastConfig == null)
                    {
                        return;
                    }
                    configToUse = _lastConfig;
                }

                try
                {
                    await StartInternalAsync(configToUse, CancellationToken.None);
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Supervised restart failed.");
                    lock (_lifecycleLock)
                    {
                        _stateMachine.TryTransitionTo(HelperStatus.Stopped, out _);
                    }
                }
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Unhandled exception in OnProcessExited supervisor callback.");
        }
    }

    public void Dispose()
    {
        lock (_lifecycleLock)
        {
            if (_isDisposed) return;
            _isDisposed = true;
        }

        _processManager.ProcessExited -= OnProcessExited;
        StopSupervised();
    }
}

