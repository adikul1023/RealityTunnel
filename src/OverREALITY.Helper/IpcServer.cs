using System;
using System.IO;
using System.IO.Pipes;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using OverREALITY.Shared.Api.VpnRuntime;

namespace OverREALITY.Helper;

public class IpcServer
{
    private const string PipeName = "OverREALITY_Helper_Pipe_v5";
    private readonly ILogger<IpcServer> _logger;
    private readonly JsonSerializerOptions _jsonOptions;

    public Func<StartVpnRequest, Task<bool>>? OnStartRequested { get; set; }
    public Func<Task<bool>>? OnStopRequested { get; set; }
    public Func<HelperStatus>? OnStatusRequested { get; set; }

    public IpcServer(ILogger<IpcServer> logger)
    {
        _logger = logger;
        _jsonOptions = new JsonSerializerOptions 
        { 
            WriteIndented = false,
            DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
            PropertyNameCaseInsensitive = true
        };
    }

    public async Task StartListeningAsync(CancellationToken cancellationToken)
    {
        while (!cancellationToken.IsCancellationRequested)
        {
            try
            {
                var pipeSecurity = new System.IO.Pipes.PipeSecurity();
                pipeSecurity.AddAccessRule(new System.IO.Pipes.PipeAccessRule(
                    new System.Security.Principal.SecurityIdentifier(System.Security.Principal.WellKnownSidType.WorldSid, null),
                    System.IO.Pipes.PipeAccessRights.ReadWrite,
                    System.Security.AccessControl.AccessControlType.Allow));
                
                using var serverStream = System.IO.Pipes.NamedPipeServerStreamAcl.Create(
                    PipeName, 
                    System.IO.Pipes.PipeDirection.InOut, 
                    NamedPipeServerStream.MaxAllowedServerInstances, 
                    System.IO.Pipes.PipeTransmissionMode.Byte, 
                    System.IO.Pipes.PipeOptions.Asynchronous, 
                    0, 0, pipeSecurity);
                
                _logger.LogInformation("Waiting for IPC connection...");
                await serverStream.WaitForConnectionAsync(cancellationToken);
                _logger.LogInformation("IPC client connected.");

                // Read length prefix (4 bytes)
                var lengthBytes = new byte[4];
                try
                {
                    await serverStream.ReadExactlyAsync(lengthBytes, cancellationToken);
                }
                catch (EndOfStreamException)
                {
                    _logger.LogWarning("IPC client disconnected before sending request length prefix.");
                    continue;
                }

                var requestLength = BitConverter.ToInt32(lengthBytes, 0);
                if (requestLength <= 0 || requestLength > 10 * 1024 * 1024)
                {
                    _logger.LogWarning("Invalid request length received: {Length}", requestLength);
                    continue;
                }

                var requestBytes = new byte[requestLength];
                try
                {
                    await serverStream.ReadExactlyAsync(requestBytes, cancellationToken);
                }
                catch (EndOfStreamException)
                {
                    _logger.LogWarning("IPC client disconnected before sending full request payload.");
                    continue;
                }

                var requestJson = Encoding.UTF8.GetString(requestBytes);
                var request = JsonSerializer.Deserialize<IpcMessage>(requestJson, _jsonOptions);

                if (request != null)
                {
                    await HandleRequestAsync(serverStream, request, cancellationToken);
                }
            }
            catch (OperationCanceledException)
            {
                break;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error handling IPC connection.");
                await Task.Delay(1000, cancellationToken); // Backoff on error
            }
        }
    }

    private async Task HandleRequestAsync(NamedPipeServerStream stream, IpcMessage request, CancellationToken cancellationToken)
    {
        object? resultData = null;
        bool success = true;
        string? error = null;

        try
        {
            switch (request.Action)
            {
                case "Start":
                    if (OnStartRequested != null && request.Payload != null)
                    {
                        var startReq = JsonSerializer.Deserialize<StartVpnRequest>(request.Payload, _jsonOptions);
                        if (startReq != null)
                            resultData = await OnStartRequested(startReq);
                        else
                            throw new Exception("Invalid Start payload.");
                    }
                    break;
                case "Stop":
                    if (OnStopRequested != null)
                        resultData = await OnStopRequested();
                    break;
                case "GetStatus":
                    if (OnStatusRequested != null)
                        resultData = OnStatusRequested();
                    break;
                case "Ping":
                    resultData = true;
                    break;
                default:
                    success = false;
                    error = "Unknown action.";
                    break;
            }
        }
        catch (Exception ex)
        {
            success = false;
            error = ex.Message;
        }

        var response = new IpcResponse<object>
        {
            Success = success,
            Data = resultData,
            ErrorMessage = error
        };

        var responseJson = JsonSerializer.Serialize(response, _jsonOptions);
        var responseBytes = Encoding.UTF8.GetBytes(responseJson);

        var lengthBytes = BitConverter.GetBytes(responseBytes.Length);
        await stream.WriteAsync(lengthBytes, cancellationToken);
        await stream.WriteAsync(responseBytes, cancellationToken);
        await stream.FlushAsync(cancellationToken);

        try
        {
            stream.WaitForPipeDrain();
        }
        catch (Exception ex)
        {
            _logger.LogDebug(ex, "WaitForPipeDrain finished or client disconnected.");
        }
    }

    private class IpcMessage
    {
        public int ProtocolVersion { get; set; } = 1;
        public string Action { get; set; } = string.Empty;
        public string? Payload { get; set; }
    }

    private class IpcResponse<T>
    {
        public int ProtocolVersion { get; set; } = 1;
        public bool Success { get; set; }
        public T? Data { get; set; }
        public string? ErrorMessage { get; set; }
        public string? ErrorCode { get; set; }
    }
}
