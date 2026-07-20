using System;
using System.IO;
using System.IO.Pipes;
using System.Security.Cryptography;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Hosting;
using RealityTunnel.Models;
using RealityTunnel.Services;
using RealityTunnel.Shared;

namespace RealityTunnel.Helper;

public class PipeServerWorker : BackgroundService
{
    private readonly HelperLogger _logger;
    private readonly PipeSecurityHelper _pipeSecurityHelper;
    private readonly IXrayController _xrayController;

    private readonly object _stateLock = new();
    private string _desiredState = "Disconnected";
    private VpnProfile? _desiredProfile = null;
    private string _actualState = "Disconnected";
    private DateTimeOffset? _connectedSince = null;
    private string? _lastError = null;

    private readonly SemaphoreSlim _wakeupSignal = new(0);

    public PipeServerWorker(HelperLogger logger, PipeSecurityHelper pipeSecurityHelper)
        : this(logger, pipeSecurityHelper, new XrayController())
    {
    }

    public PipeServerWorker(HelperLogger logger, PipeSecurityHelper pipeSecurityHelper, IXrayController xrayController)
    {
        _logger = logger;
        _pipeSecurityHelper = pipeSecurityHelper;
        _xrayController = xrayController;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        _logger.LogInfo("PipeServerWorker starting. Listening on \\\\.\\pipe\\RealityTunnelHelper");
        var pipeSecurity = _pipeSecurityHelper.CreatePipeSecurity();

        var reconTask = Task.Run(() => RunReconciliationLoopAsync(stoppingToken), stoppingToken);

        while (!stoppingToken.IsCancellationRequested)
        {
            NamedPipeServerStream? pipeServer = null;
            try
            {
                pipeServer = NamedPipeServerStreamAcl.Create(
                    "RealityTunnelHelper",
                    PipeDirection.InOut,
                    NamedPipeServerStream.MaxAllowedServerInstances,
                    PipeTransmissionMode.Byte,
                    PipeOptions.Asynchronous,
                    4096,
                    4096,
                    pipeSecurity);

                await pipeServer.WaitForConnectionAsync(stoppingToken);

                _ = HandleClientAsync(pipeServer, stoppingToken);
            }
            catch (OperationCanceledException)
            {
                pipeServer?.Dispose();
                break;
            }
            catch (Exception ex)
            {
                _logger.LogError("Error accepting pipe client connection.", ex);
                pipeServer?.Dispose();
                await Task.Delay(1000, stoppingToken);
            }
        }

        _logger.LogInfo("PipeServerWorker stopped.");
    }

    private async Task RunReconciliationLoopAsync(CancellationToken stoppingToken)
    {
        _logger.LogInfo("Reconciliation loop starting. Initializing orphan cleanup on service startup.");
        PerformOrphanCleanup();

        int backoffMs = 2000;
        const int maxBackoffMs = 60000;
        DateTimeOffset? lastStartSuccessTime = null;

        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                string desired;
                VpnProfile? profile;
                lock (_stateLock)
                {
                    desired = _desiredState;
                    profile = _desiredProfile;
                }

                if (desired == "Disconnected")
                {
                    bool isRunning = _xrayController.IsRunning() || HasOrphanSingBoxProcesses();
                    if (isRunning)
                    {
                        _logger.LogInfo("Reconciliation: Desired state is Disconnected but sing-box is active or orphaned. Tearing down.");
                        PerformOrphanCleanup();
                    }

                    lock (_stateLock)
                    {
                        _actualState = "Disconnected";
                        _connectedSince = null;
                    }
                    backoffMs = 2000;
                    lastStartSuccessTime = null;
                }
                else if (desired == "Connected" && profile != null)
                {
                    if (_xrayController.IsRunning())
                    {
                        lock (_stateLock)
                        {
                            _actualState = "Connected";
                            if (_connectedSince == null) _connectedSince = DateTimeOffset.UtcNow;
                        }

                        if (lastStartSuccessTime.HasValue && (DateTimeOffset.UtcNow - lastStartSuccessTime.Value).TotalSeconds > 30)
                        {
                            backoffMs = 2000;
                        }
                    }
                    else
                    {
                        _logger.LogInfo($"Reconciliation: sing-box not running while desired state is Connected. Launching for profile '{profile.ServerHost}:{profile.ServerPort}'...");
                        lock (_stateLock)
                        {
                            _actualState = "Connecting";
                        }

                        PerformOrphanCleanup();

                        try
                        {
                            _xrayController.Start(profile);
                            _logger.LogInfo("sing-box started successfully via IXrayController.");
                            lock (_stateLock)
                            {
                                _actualState = "Connected";
                                _connectedSince = DateTimeOffset.UtcNow;
                                _lastError = null;
                            }
                            lastStartSuccessTime = DateTimeOffset.UtcNow;
                            backoffMs = 2000;
                        }
                        catch (Exception ex)
                        {
                            _logger.LogError($"Failed to start sing-box during reconciliation: {ex.Message}");
                            lock (_stateLock)
                            {
                                _actualState = "Failed";
                                _lastError = ex.Message;
                                _connectedSince = null;
                            }
                            _logger.LogWarn($"Reconciliation backing off for {backoffMs}ms before next attempt.");
                            await WaitWithWakeupAsync(backoffMs, stoppingToken);
                            backoffMs = Math.Min(backoffMs * 2, maxBackoffMs);
                            continue;
                        }
                    }
                }

                await WaitWithWakeupAsync(2000, stoppingToken);
            }
            catch (OperationCanceledException)
            {
                break;
            }
            catch (Exception ex)
            {
                _logger.LogError("Unhandled error in reconciliation loop tick.", ex);
                await WaitWithWakeupAsync(2000, stoppingToken);
            }
        }

        _logger.LogInfo("Reconciliation loop stopping. Performing final teardown.");
        PerformOrphanCleanup();
    }

    private async Task WaitWithWakeupAsync(int millisecondsTimeout, CancellationToken stoppingToken)
    {
        try
        {
            await _wakeupSignal.WaitAsync(millisecondsTimeout, stoppingToken);
        }
        catch (OperationCanceledException) { }
    }

    private void WakeupReconciliationLoop()
    {
        try
        {
            if (_wakeupSignal.CurrentCount == 0)
            {
                _wakeupSignal.Release();
            }
        }
        catch { }
    }

    private void PerformOrphanCleanup()
    {
        try
        {
            _xrayController.Stop();
        }
        catch (Exception ex)
        {
            _logger.LogWarn($"Error stopping tracked XrayController during orphan cleanup: {ex.Message}");
        }

        try
        {
            foreach (var orphan in System.Diagnostics.Process.GetProcessesByName("sing-box"))
            {
                try { orphan.Kill(entireProcessTree: true); orphan.WaitForExit(3000); } catch { }
                orphan.Dispose();
            }
        }
        catch (Exception ex)
        {
            _logger.LogWarn($"Error killing orphan sing-box processes: {ex.Message}");
        }
    }

    private bool HasOrphanSingBoxProcesses()
    {
        try
        {
            var procs = System.Diagnostics.Process.GetProcessesByName("sing-box");
            bool hasOrphans = procs.Length > 0;
            foreach (var p in procs) p.Dispose();
            return hasOrphans;
        }
        catch
        {
            return false;
        }
    }

    private async Task HandleClientAsync(NamedPipeServerStream pipeStream, CancellationToken stoppingToken)
    {
        string sessionToken = "";
        long lastSeenSequence = 0;
        string clientIdentity = "Unknown";
        uint clientPid = 0;

        using (pipeStream)
        {
            try
            {
                var firstMsg = await IpcFraming.ReadMessageAsync(pipeStream, stoppingToken);
                if (firstMsg == null)
                {
                    return;
                }

                if (!_pipeSecurityHelper.ValidateClientConnection(pipeStream, out clientIdentity, out clientPid, out string clientPath))
                {
                    _logger.LogWarn("Client connection validation failed after initial read. Rejecting pipe client.");
                    await SendErrorAsync(pipeStream, IpcErrorCodes.Unauthorized, "Client validation failed or unauthorized identity.", firstMsg.RequestId, stoppingToken);
                    return;
                }

                if (firstMsg.Type != IpcMessageTypes.Hello)
                {
                    _logger.LogWarn($"First message from PID {clientPid} ({clientIdentity}) was not Hello. Closing connection.");
                    await SendErrorAsync(pipeStream, IpcErrorCodes.HandshakeRequired, "Hello must be negotiated before any other command.", firstMsg.RequestId, stoppingToken);
                    return;
                }

                if (firstMsg.ProtocolVersion != 1)
                {
                    _logger.LogWarn($"Client PID {clientPid} requested unsupported protocol version: {firstMsg.ProtocolVersion}");
                    await SendErrorAsync(pipeStream, IpcErrorCodes.VersionMismatch, $"Unsupported protocol version: {firstMsg.ProtocolVersion}", firstMsg.RequestId, stoppingToken);
                    return;
                }

                sessionToken = Convert.ToHexString(RandomNumberGenerator.GetBytes(32));
                lastSeenSequence = firstMsg.Sequence;

                var helloResp = new HelloResponse
                {
                    SessionToken = sessionToken,
                    ServiceVersion = "1.0.0"
                };
                await SendMessageAsync(pipeStream, IpcMessage.Create(IpcMessageTypes.Ack, helloResp, sessionToken, lastSeenSequence, firstMsg.RequestId), stoppingToken);
                _logger.LogInfo($"Hello handshake completed for PID {clientPid} ({clientIdentity}). Session established.");

                while (!stoppingToken.IsCancellationRequested && pipeStream.IsConnected)
                {
                    var msg = await IpcFraming.ReadMessageAsync(pipeStream, stoppingToken);
                    if (msg == null)
                    {
                        _logger.LogInfo($"Client PID {clientPid} disconnected cleanly.");
                        break;
                    }

                    if (msg.SessionToken != sessionToken)
                    {
                        _logger.LogWarn($"Client PID {clientPid} sent message with invalid session token. Closing connection.");
                        await SendErrorAsync(pipeStream, IpcErrorCodes.Unauthorized, "Invalid session token.", msg.RequestId, stoppingToken);
                        break;
                    }

                    if (msg.Sequence != lastSeenSequence + 1)
                    {
                        _logger.LogWarn($"Client PID {clientPid} sequence mismatch. Expected {lastSeenSequence + 1}, got {msg.Sequence}. Closing connection.");
                        await SendErrorAsync(pipeStream, IpcErrorCodes.InvalidSequence, $"Expected sequence {lastSeenSequence + 1}, got {msg.Sequence}.", msg.RequestId, stoppingToken);
                        break;
                    }

                    lastSeenSequence = msg.Sequence;
                    await ProcessMessageAsync(pipeStream, msg, stoppingToken);
                }
            }
            catch (EndOfStreamException)
            {
                _logger.LogInfo($"Client PID {clientPid} stream ended.");
            }
            catch (OperationCanceledException) { }
            catch (Exception ex)
            {
                _logger.LogError($"Unhandled error handling pipe client PID {clientPid}.", ex);
            }
        }
    }

    private async Task ProcessMessageAsync(NamedPipeServerStream pipeStream, IpcMessage msg, CancellationToken stoppingToken)
    {
        switch (msg.Type)
        {
            case IpcMessageTypes.Ping:
                await SendMessageAsync(pipeStream, IpcMessage.CreateEmpty(IpcMessageTypes.Ack, msg.SessionToken, msg.Sequence, msg.RequestId), stoppingToken);
                break;

            case IpcMessageTypes.GetStatus:
                GetStatusResponse statusResp;
                lock (_stateLock)
                {
                    statusResp = new GetStatusResponse
                    {
                        DesiredState = _desiredState,
                        ActualState = _actualState,
                        ConnectedSince = _connectedSince,
                        LastError = _lastError
                    };
                }
                await SendMessageAsync(pipeStream, IpcMessage.Create(IpcMessageTypes.Ack, statusResp, msg.SessionToken, msg.Sequence, msg.RequestId), stoppingToken);
                break;

            case IpcMessageTypes.Connect:
                var profile = msg.GetPayload<VpnProfile>();
                if (profile == null || string.IsNullOrEmpty(profile.ServerHost))
                {
                    await SendErrorAsync(pipeStream, IpcErrorCodes.OperationFailed, "Invalid or missing VpnProfile.", msg.RequestId, stoppingToken);
                    return;
                }
                _logger.LogInfo($"Received Connect command for profile '{profile.ServerHost}:{profile.ServerPort}'. Setting desired state to Connected.");
                lock (_stateLock)
                {
                    _desiredState = "Connected";
                    _desiredProfile = profile;
                    if (_actualState != "Connected")
                    {
                        _actualState = "Connecting";
                    }
                    _lastError = null;
                }
                WakeupReconciliationLoop();
                await SendMessageAsync(pipeStream, IpcMessage.CreateEmpty(IpcMessageTypes.Ack, msg.SessionToken, msg.Sequence, msg.RequestId), stoppingToken);
                break;

            case IpcMessageTypes.Disconnect:
                _logger.LogInfo("Received Disconnect command. Setting desired state to Disconnected.");
                lock (_stateLock)
                {
                    _desiredState = "Disconnected";
                    _desiredProfile = null;
                    if (_actualState != "Disconnected")
                    {
                        _actualState = "Disconnecting";
                    }
                }
                WakeupReconciliationLoop();
                await SendMessageAsync(pipeStream, IpcMessage.CreateEmpty(IpcMessageTypes.Ack, msg.SessionToken, msg.Sequence, msg.RequestId), stoppingToken);
                break;

            case IpcMessageTypes.GetHelperLog:
                var tail = _logger.GetLogTail(100);
                await SendMessageAsync(pipeStream, IpcMessage.Create(IpcMessageTypes.Ack, tail, msg.SessionToken, msg.Sequence, msg.RequestId), stoppingToken);
                break;

            default:
                _logger.LogWarn($"Unknown command type received: '{msg.Type}'");
                await SendErrorAsync(pipeStream, IpcErrorCodes.OperationFailed, $"Unknown command: {msg.Type}", msg.RequestId, stoppingToken);
                break;
        }
    }

    private async Task SendMessageAsync(NamedPipeServerStream pipeStream, IpcMessage message, CancellationToken stoppingToken)
    {
        await IpcFraming.WriteMessageAsync(pipeStream, message, stoppingToken);
    }

    private async Task SendErrorAsync(NamedPipeServerStream pipeStream, string errorCode, string errorMessage, string? requestId, CancellationToken stoppingToken)
    {
        var errPayload = new ErrorResponse { ErrorCode = errorCode, Message = errorMessage };
        var errMsg = IpcMessage.Create(IpcMessageTypes.Error, errPayload, null, 0, requestId);
        try
        {
            await SendMessageAsync(pipeStream, errMsg, stoppingToken);
        }
        catch { }
    }

    public override void Dispose()
    {
        _wakeupSignal.Dispose();
        base.Dispose();
    }
}
