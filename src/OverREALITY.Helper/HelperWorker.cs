using System;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using OverREALITY.Shared.Api.VpnRuntime;

namespace OverREALITY.Helper;

public class HelperWorker : BackgroundService
{
    private readonly IpcServer _ipcServer;
    private readonly HelperStateMachine _stateMachine;
    private readonly ProcessSupervisor _supervisor;
    private readonly ILogger<HelperWorker> _logger;

    public HelperWorker(
        IpcServer ipcServer, 
        HelperStateMachine stateMachine, 
        ProcessSupervisor supervisor, 
        ILogger<HelperWorker> logger)
    {
        _ipcServer = ipcServer;
        _stateMachine = stateMachine;
        _supervisor = supervisor;
        _logger = logger;

        _ipcServer.OnStartRequested = async (req) => 
        {
            try
            {
                await _supervisor.StartSupervisedAsync(req.Config.JsonConfig);
                return true;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to start VPN.");
                if (_stateMachine.CurrentStatus == HelperStatus.Starting)
                {
                    _stateMachine.TransitionTo(HelperStatus.Stopped);
                }
                throw;
            }
        };

        _ipcServer.OnStopRequested = () =>
        {
            try
            {
                _stateMachine.TransitionTo(HelperStatus.Stopping);
                _supervisor.StopSupervised();
                _stateMachine.TransitionTo(HelperStatus.Stopped);
                return Task.FromResult(true);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to stop VPN.");
                return Task.FromResult(false);
            }
        };

        _ipcServer.OnStatusRequested = () => _stateMachine.CurrentStatus;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        _logger.LogInformation("HelperWorker running.");

        try
        {
            await _ipcServer.StartListeningAsync(stoppingToken);
        }
        catch (OperationCanceledException)
        {
            // Normal shutdown
        }
        catch (Exception ex)
        {
            _logger.LogCritical(ex, "IPC server crashed.");
        }
    }

    public override async Task StopAsync(CancellationToken cancellationToken)
    {
        _logger.LogInformation("HelperWorker stopping.");
        if (_stateMachine.CurrentStatus == HelperStatus.Running)
        {
            _supervisor.StopSupervised();
        }
        await base.StopAsync(cancellationToken);
    }
}
