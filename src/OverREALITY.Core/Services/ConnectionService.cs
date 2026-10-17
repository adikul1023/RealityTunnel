using System;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using OverREALITY.Shared.Api;
using OverREALITY.Shared.Api.VpnRuntime;
using OverREALITY.Shared.Interfaces;
using System.Diagnostics;

namespace OverREALITY.Core.Services;

public class ConnectionService : IConnectionService
{
    private readonly IConnectionStateManager _stateManager;
    private readonly IConnectionProvisioningService _provisioningService;
    private readonly IHelperClient _helperClient;
    private readonly IOperationContext _operationContext;
    private readonly IAuthService _authService;
    private readonly IApiClient _apiClient;
    private readonly ILogger<ConnectionService> _logger;
    private readonly SemaphoreSlim _connectionLock = new(1, 1);
    private CancellationTokenSource? _pollingCts;
    private Task? _pollingTask;
    private Process? _vpnHoodProcess;

    public ConnectionService(
        IConnectionStateManager stateManager,
        IConnectionProvisioningService provisioningService,
        IHelperClient helperClient,
        IOperationContext operationContext,
        IAuthService authService,
        IApiClient apiClient,
        ILogger<ConnectionService> logger)
    {
        _stateManager = stateManager;
        _provisioningService = provisioningService;
        _helperClient = helperClient;
        _operationContext = operationContext;
        _authService = authService;
        _apiClient = apiClient;
        _logger = logger;
    }

    public async Task ConnectAsync(int serverIndex = 0, CancellationToken cancellationToken = default)
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
                if (serverIndex == 1)
                {
                    _logger.LogInformation("Connecting to Oracle (VPNHood) via external client process.");
                    _stateManager.SetState(ConnectionState.StartingHelper);
                    
                    var baseDir = AppDomain.CurrentDomain.BaseDirectory;
                    var clientExePath = System.IO.Path.Combine(baseDir, "VpnHoodClient", "VpnHoodClient.exe");
                    
                    _logger.LogInformation("Requesting VPNHood token from backend...");
                    var tokenResult = await _apiClient.PostAsync<object, OverREALITY.Shared.Api.VpnHoodTokenResponse>("/api/client/vpnhood/token", new { }, cancellationToken);
                    if (!tokenResult.IsSuccess || tokenResult.Value == null)
                    {
                        _logger.LogError("Failed to provision VPNHood token. {Message}", tokenResult.Error?.Message);
                        _stateManager.SetState(ConnectionState.Failed, "Failed to provision VPNHood connection.");
                        return;
                    }
                    var accessKey = tokenResult.Value.AccessKey;
                    if (!System.IO.File.Exists(clientExePath))
                    {
                        _logger.LogError($"VPNHood client EXE not found at {clientExePath}");
                        _stateManager.SetState(ConnectionState.Failed, "VPNHood client not built/found.");
                        return;
                    }

                    _vpnHoodProcess = new Process
                    {
                        StartInfo = new ProcessStartInfo
                        {
                            FileName = clientExePath,
                            Arguments = $"-c \"{accessKey}\"",
                            UseShellExecute = true,
                            WindowStyle = ProcessWindowStyle.Normal // Let user see the VPNHood UI or console for testing
                        }
                    };

                    _vpnHoodProcess.Start();

                    _stateManager.SetState(ConnectionState.Connected);
                    _logger.LogInformation("VPNHood process started successfully.");
                    return;
                }

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
            _logger.LogInformation("Starting disconnect sequence.");
            
            StopStatusPolling();

            try
            {
                _stateManager.SetState(ConnectionState.Disconnecting);
                
                if (_vpnHoodProcess != null && !_vpnHoodProcess.HasExited)
                {
                    _logger.LogInformation("Disconnecting VPNHood client (killing process).");
                    _vpnHoodProcess.Kill();
                    _vpnHoodProcess.Dispose();
                    _vpnHoodProcess = null;
                }
                else
                {
                    var helperResult = await _helperClient.StopAsync(cancellationToken);
                    if (!helperResult.IsSuccess)
                    {
                        _logger.LogWarning("Helper reported failure while stopping: {Message}", helperResult.Error?.Message);
                    }
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
