using System;
using System.Collections.Concurrent;
using System.IO;
using System.IO.Pipes;
using System.Threading;
using System.Threading.Tasks;
using RealityTunnel.Models;
using RealityTunnel.Shared;

namespace RealityTunnel.Services;

public class NamedPipeVpnBackend : IVpnBackend, IDisposable
{
    private const string PipeName = "RealityTunnelHelper";
    private const string ServerName = ".";

    private NamedPipeClientStream? _pipeStream;
    private string? _sessionToken;
    private long _sequence = 0;
    private readonly SemaphoreSlim _writeLock = new SemaphoreSlim(1, 1);
    private readonly SemaphoreSlim _connectLock = new SemaphoreSlim(1, 1);
    private readonly ConcurrentDictionary<string, TaskCompletionSource<IpcMessage>> _pendingRequests = new();
    private CancellationTokenSource? _readLoopCts;

    public async Task ConnectAsync(VpnProfile profile)
    {
        System.Diagnostics.Debug.WriteLine($"[UI/IPC] Sending Connect request for profile '{profile.ServerHost}:{profile.ServerPort}'...");
        await EnsureConnectedAsync(CancellationToken.None);

        var msg = CreateMessage(IpcMessageTypes.Connect, profile);
        var response = await SendRequestAsync(msg, CancellationToken.None);

        if (response.Type == IpcMessageTypes.Error)
        {
            var err = response.GetPayload<ErrorResponse>();
            System.Diagnostics.Debug.WriteLine($"[UI/IPC] Connect rejected by Helper: [{err?.ErrorCode}] {err?.Message}");
            throw new InvalidOperationException($"Service failed to connect: [{err?.ErrorCode}] {err?.Message}");
        }
        System.Diagnostics.Debug.WriteLine("[UI/IPC] Connect command acknowledged by Helper.");
    }

    public async Task DisconnectAsync()
    {
        try
        {
            System.Diagnostics.Debug.WriteLine("[UI/IPC] Sending Disconnect command to Helper...");
            await EnsureConnectedAsync(CancellationToken.None);

            var msg = CreateMessageEmpty(IpcMessageTypes.Disconnect);
            await SendRequestAsync(msg, CancellationToken.None);
            System.Diagnostics.Debug.WriteLine("[UI/IPC] Disconnect command acknowledged by Helper.");
        }
        catch (Exception ex)
        {
            System.Diagnostics.Debug.WriteLine($"[UI/IPC] Disconnect IPC failed or pipe closed: {ex.Message}");
        }
    }

    public async Task<bool> IsRunningAsync()
    {
        try
        {
            await EnsureConnectedAsync(CancellationToken.None);

            var msg = CreateMessageEmpty(IpcMessageTypes.GetStatus);
            var response = await SendRequestAsync(msg, CancellationToken.None);

            if (response.Type == IpcMessageTypes.Error)
            {
                return false;
            }

            var status = response.GetPayload<GetStatusResponse>();
            return status?.ActualState == "Connected" || status?.DesiredState == "Connected";
        }
        catch
        {
            return false;
        }
    }

    public async Task<bool> PingAsync(CancellationToken cancellationToken = default)
    {
        try
        {
            await EnsureConnectedAsync(cancellationToken);
            var msg = CreateMessageEmpty(IpcMessageTypes.Ping);
            var response = await SendRequestAsync(msg, cancellationToken);
            return response.Type == IpcMessageTypes.Ack;
        }
        catch
        {
            return false;
        }
    }

    public async Task<GetStatusResponse?> GetStatusAsync(CancellationToken cancellationToken = default)
    {
        try
        {
            await EnsureConnectedAsync(cancellationToken);
            var msg = CreateMessageEmpty(IpcMessageTypes.GetStatus);
            var response = await SendRequestAsync(msg, cancellationToken);
            return response.GetPayload<GetStatusResponse>();
        }
        catch
        {
            return null;
        }
    }

    private async Task EnsureConnectedAsync(CancellationToken cancellationToken)
    {
        if (_pipeStream != null && _pipeStream.IsConnected && !string.IsNullOrEmpty(_sessionToken))
        {
            return;
        }

        await _connectLock.WaitAsync(cancellationToken);
        try
        {
            if (_pipeStream != null && _pipeStream.IsConnected && !string.IsNullOrEmpty(_sessionToken))
            {
                return;
            }

            CleanupPipe();

            _pipeStream = new NamedPipeClientStream(ServerName, PipeName, PipeDirection.InOut, PipeOptions.Asynchronous);
            await _pipeStream.ConnectAsync(5000, cancellationToken);

            _sequence = 1;
            System.Diagnostics.Debug.WriteLine("[UI/IPC] Connected to named pipe. Performing Hello handshake...");
            var helloReq = new HelloRequest { ClientPid = Environment.ProcessId };
            var helloMsg = IpcMessage.Create(IpcMessageTypes.Hello, helloReq, null, _sequence++);

            await _writeLock.WaitAsync(cancellationToken);
            try
            {
                await IpcFraming.WriteMessageAsync(_pipeStream, helloMsg, cancellationToken);
            }
            finally
            {
                _writeLock.Release();
            }

            var resp = await IpcFraming.ReadMessageAsync(_pipeStream, cancellationToken);
            if (resp == null || resp.Type != IpcMessageTypes.Ack)
            {
                if (resp?.Type == IpcMessageTypes.Error)
                {
                    var err = resp.GetPayload<ErrorResponse>();
                    System.Diagnostics.Debug.WriteLine($"[UI/IPC] Hello handshake rejected: [{err?.ErrorCode}] {err?.Message}");
                    throw new InvalidOperationException($"Hello handshake rejected by Helper service: [{err?.ErrorCode}] {err?.Message}");
                }
                throw new InvalidOperationException($"Hello handshake failed. Expected Ack, received '{resp?.Type ?? "null"}'.");
            }

            var helloResp = resp.GetPayload<HelloResponse>();
            if (helloResp == null || string.IsNullOrEmpty(helloResp.SessionToken))
            {
                throw new InvalidOperationException("Hello response missing session token.");
            }

            _sessionToken = helloResp.SessionToken;
            System.Diagnostics.Debug.WriteLine($"[UI/IPC] Hello handshake successful. SessionToken established: {_sessionToken.Substring(0, 8)}...");
            _readLoopCts = new CancellationTokenSource();
            _ = ReadLoopAsync(_pipeStream, _readLoopCts.Token);
        }
        finally
        {
            _connectLock.Release();
        }
    }

    private async Task ReadLoopAsync(NamedPipeClientStream stream, CancellationToken cancellationToken)
    {
        try
        {
            while (!cancellationToken.IsCancellationRequested && stream.IsConnected)
            {
                var msg = await IpcFraming.ReadMessageAsync(stream, cancellationToken);
                if (msg == null) break;

                if (!string.IsNullOrEmpty(msg.RequestId) && _pendingRequests.TryRemove(msg.RequestId, out var tcs))
                {
                    tcs.TrySetResult(msg);
                }
            }
        }
        catch (OperationCanceledException) { }
        catch (Exception ex)
        {
            System.Diagnostics.Debug.WriteLine($"[UI/IPC] NamedPipe client read loop error: {ex.Message}");
        }
        finally
        {
            CleanupPipe();
        }
    }

    private async Task<IpcMessage> SendRequestAsync(IpcMessage request, CancellationToken cancellationToken)
    {
        if (_pipeStream == null || !_pipeStream.IsConnected)
        {
            throw new InvalidOperationException("Pipe is not connected.");
        }

        var tcs = new TaskCompletionSource<IpcMessage>(TaskCreationOptions.RunContinuationsAsynchronously);
        _pendingRequests[request.RequestId] = tcs;

        await _writeLock.WaitAsync(cancellationToken);
        try
        {
            await IpcFraming.WriteMessageAsync(_pipeStream, request, cancellationToken);
        }
        catch
        {
            _pendingRequests.TryRemove(request.RequestId, out _);
            _writeLock.Release();
            throw;
        }
        _writeLock.Release();

        using var timeoutCts = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        timeoutCts.CancelAfter(TimeSpan.FromSeconds(10));

        using var reg = timeoutCts.Token.Register(() =>
        {
            if (_pendingRequests.TryRemove(request.RequestId, out var timedOutTcs))
            {
                timedOutTcs.TrySetException(new TimeoutException($"IPC request '{request.Type}' timed out after 10 seconds."));
            }
        });

        return await tcs.Task;
    }

    private IpcMessage CreateMessage<T>(string type, T payload)
    {
        return IpcMessage.Create(type, payload, _sessionToken, _sequence++);
    }

    private IpcMessage CreateMessageEmpty(string type)
    {
        return IpcMessage.CreateEmpty(type, _sessionToken, _sequence++);
    }

    private void CleanupPipe()
    {
        _readLoopCts?.Cancel();
        _readLoopCts?.Dispose();
        _readLoopCts = null;

        _pipeStream?.Dispose();
        _pipeStream = null;
        _sessionToken = null;

        foreach (var kvp in _pendingRequests)
        {
            kvp.Value.TrySetException(new IOException("Pipe connection closed."));
        }
        _pendingRequests.Clear();
    }

    public void Dispose()
    {
        CleanupPipe();
        _writeLock.Dispose();
        _connectLock.Dispose();
    }
}
