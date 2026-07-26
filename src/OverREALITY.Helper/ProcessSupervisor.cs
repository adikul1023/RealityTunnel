using System;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using OverREALITY.Shared.Api.VpnRuntime;

namespace OverREALITY.Helper;

public class ProcessSupervisor
{
    private readonly SingboxProcessManager _processManager;
    private readonly HelperStateMachine _stateMachine;
    private readonly ILogger<ProcessSupervisor> _logger;
    private int _crashCount;
    private const int MaxCrashes = 3;
    private string? _lastConfig;

    public ProcessSupervisor(SingboxProcessManager processManager, HelperStateMachine stateMachine, ILogger<ProcessSupervisor> logger)
    {
        _processManager = processManager;
        _stateMachine = stateMachine;
        _logger = logger;
        
        _processManager.ProcessExited += OnProcessExited;
    }

    public async Task StartSupervisedAsync(string configJson, CancellationToken cancellationToken = default)
    {
        var currentStatus = _stateMachine.CurrentStatus;
        if (currentStatus == HelperStatus.Running || currentStatus == HelperStatus.Starting)
        {
            throw new InvalidOperationException($"VPN is already {currentStatus}.");
        }
        
        _crashCount = 0;
        _lastConfig = configJson;
        await StartInternalAsync(configJson, cancellationToken);
    }

    public void StopSupervised()
    {
        _processManager.Stop();
    }

    private async Task StartInternalAsync(string configJson, CancellationToken cancellationToken)
    {
        _stateMachine.TransitionTo(HelperStatus.Starting);
        try
        {
            await _processManager.StartAsync(configJson, cancellationToken);
            _stateMachine.TransitionTo(HelperStatus.Running);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to start VPN process.");
            _stateMachine.TransitionTo(HelperStatus.Stopped);
            throw;
        }
    }

    private async void OnProcessExited(object? sender, ProcessExitedEventArgs e)
    {
        var status = _stateMachine.CurrentStatus;
        if (status == HelperStatus.Running || status == HelperStatus.Starting)
        {
            _logger.LogWarning("Process exited unexpectedly (Code: {Code}, Runtime: {Runtime}).", e.ExitCode, e.Runtime);
            
            _stateMachine.TransitionTo(HelperStatus.Crashed);
            _crashCount++;

            if (_crashCount > MaxCrashes)
            {
                _logger.LogCritical("Maximum crash count exceeded. Giving up.");
                _stateMachine.TransitionTo(HelperStatus.Stopped);
                return;
            }

            _logger.LogInformation("Attempting restart {Count} of {Max}.", _crashCount, MaxCrashes);
            _stateMachine.TransitionTo(HelperStatus.Restarting);
            
            // Exponential backoff
            await Task.Delay(TimeSpan.FromSeconds(Math.Pow(2, _crashCount)));
            
            if (_lastConfig != null && _stateMachine.CurrentStatus == HelperStatus.Restarting)
            {
                try
                {
                    await StartInternalAsync(_lastConfig, CancellationToken.None);
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Restart failed.");
                }
            }
        }
    }
}
