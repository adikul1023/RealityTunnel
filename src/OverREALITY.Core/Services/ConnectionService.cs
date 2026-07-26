using System;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using OverREALITY.Shared.Api;
using OverREALITY.Shared.Api.VpnRuntime;
using OverREALITY.Shared.Interfaces;

namespace OverREALITY.Core.Services;

public class ConnectionService : IConnectionService
{
    private readonly IConnectionStateManager _stateManager;
    private readonly IConnectionProvisioningService _provisioningService;
    private readonly IHelperClient _helperClient;
    private readonly IOperationContext _operationContext;
    private readonly IAuthService _authService;
    private readonly ILogger<ConnectionService> _logger;
    private readonly SemaphoreSlim _connectionLock = new(1, 1);
    private CancellationTokenSource? _pollingCts;
    private Task? _pollingTask;

    public ConnectionService(
        IConnectionStateManager stateManager,
        IConnectionProvisioningService provisioningService,
        IHelperClient helperClient,
        IOperationContext operationContext,
        IAuthService authService,
        ILogger<ConnectionService> logger)
    {
        _stateManager = stateManager;
        _provisioningService = provisioningService;
        _helperClient = helperClient;
        _operationContext = operationContext;
        _authService = authService;
        _logger = logger;
    }

    public async Task ConnectAsync(CancellationToken cancellationToken = default)
    {
        if (!await _connectionLock.WaitAsync(0, cancellationToken))
        {
            _logger.LogWarning("Connection sequence is already in progress.");
            return;
        }

        try
        {
            using var operation = _operationContext.BeginOperation("Connect");
            _logger.LogInformation("Starting connection sequence.");

            try
            {
                _stateManager.SetState(ConnectionState.Provisioning);
                var provisionResult = await _provisioningService.ConnectProvisionAsync(cancellationToken);
                if (!provisionResult.IsSuccess)
                {
                    _logger.LogError("Provisioning failed: {Message}", provisionResult.Error?.Message);
                    _stateManager.SetState(ConnectionState.Failed, $"Provisioning failed: {provisionResult.Error?.Message}");
                    
                    if (provisionResult.Error?.Code == "Unauthorized" || provisionResult.Error?.Code == "Forbidden")
                    {
                        _logger.LogWarning("Device or token unauthorized. Logging out.");
                        await _authService.LogoutAsync(cancellationToken);
                    }
                    return;
                }

                _stateManager.SetState(ConnectionState.StartingHelper);
                var startRequest = new StartVpnRequest { Config = provisionResult.Value! };
                var helperResult = await _helperClient.StartAsync(startRequest, cancellationToken);

                if (!helperResult.IsSuccess)
                {
                    _logger.LogError("Helper failed to start VPN: {Message}", helperResult.Error?.Message);
                    _stateManager.SetState(ConnectionState.Failed, $"Helper startup failed: {helperResult.Error?.Message}");
                    return;
                }

                _stateManager.SetState(ConnectionState.Connected);
                _logger.LogInformation("Connection established successfully.");
                StartStatusPolling();
            }
            catch (OperationCanceledException)
            {
                _logger.LogWarning("Connection sequence was canceled.");
                _stateManager.SetState(ConnectionState.Disconnected);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Unexpected error during connection sequence.");
                _stateManager.SetState(ConnectionState.Failed, $"Unexpected error: {ex.Message}");
            }
        }
        finally
        {
            _connectionLock.Release();
        }
    }

    public async Task DisconnectAsync(CancellationToken cancellationToken = default)
    {
        if (!await _connectionLock.WaitAsync(0, cancellationToken))
        {
            _logger.LogWarning("Connection sequence is already in progress.");
            return;
        }

        try
        {
            using var operation = _operationContext.BeginOperation("Disconnect");
            _logger.LogInformation("Starting disconnection sequence.");
            
            StopStatusPolling();

            try
            {
                _stateManager.SetState(ConnectionState.Disconnecting);
                var helperResult = await _helperClient.StopAsync(cancellationToken);

                if (!helperResult.IsSuccess)
                {
                    _logger.LogWarning("Helper reported failure while stopping: {Message}", helperResult.Error?.Message);
                }

                _stateManager.SetState(ConnectionState.Disconnected);
                _logger.LogInformation("Disconnected successfully.");
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error during disconnection sequence.");
                _stateManager.SetState(ConnectionState.Failed, $"Disconnect error: {ex.Message}");
            }
        }
        finally
        {
            _connectionLock.Release();
        }
    }

    private void StartStatusPolling()
    {
        _pollingCts = new CancellationTokenSource();
        _pollingTask = Task.Run(async () => await PollStatusAsync(_pollingCts.Token));
    }

    private void StopStatusPolling()
    {
        _pollingCts?.Cancel();
        _pollingCts?.Dispose();
        _pollingCts = null;
        _pollingTask = null;
    }

    private async Task PollStatusAsync(CancellationToken cancellationToken)
    {
        while (!cancellationToken.IsCancellationRequested)
        {
            try
            {
                await Task.Delay(2000, cancellationToken);
                var statusResult = await _helperClient.GetStatusAsync(cancellationToken);
                if (statusResult.IsSuccess)
                {
                    var helperStatus = statusResult.Value;
                    if (helperStatus == HelperStatus.Restarting)
                    {
                        if (_stateManager.CurrentState != ConnectionState.Reconnecting)
                        {
                            _stateManager.SetState(ConnectionState.Reconnecting);
                        }
                    }
                    else if (helperStatus == HelperStatus.Running)
                    {
                        if (_stateManager.CurrentState != ConnectionState.Connected)
                        {
                            _stateManager.SetState(ConnectionState.Connected);
                        }
                    }
                    else if (helperStatus == HelperStatus.Stopped || helperStatus == HelperStatus.Crashed)
                    {
                        if (_stateManager.CurrentState != ConnectionState.Disconnected && _stateManager.CurrentState != ConnectionState.Failed)
                        {
                            _stateManager.SetState(ConnectionState.Failed, "VPN process crashed unexpectedly.");
                            StopStatusPolling();
                            break;
                        }
                    }
                }
            }
            catch (OperationCanceledException)
            {
                break;
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "Error polling helper status.");
            }
        }
    }
}
