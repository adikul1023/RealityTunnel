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
using OverREALITY.Shared.Errors;
using OverREALITY.Shared.Interfaces;

namespace OverREALITY.Infrastructure.Services;

public class HelperClient : IHelperClient
{
    private const string PipeName = "OverREALITY_Helper_Pipe_v5";
    private readonly ILogger<HelperClient> _logger;
    private readonly JsonSerializerOptions _jsonOptions;

    public HelperClient(ILogger<HelperClient> logger)
    {
        _logger = logger;
        _jsonOptions = new JsonSerializerOptions 
        { 
            WriteIndented = false,
            DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
            PropertyNameCaseInsensitive = true
        };
    }

    public async Task<Result<bool, HelperError>> StartAsync(StartVpnRequest request, CancellationToken cancellationToken = default)
    {
        return await SendRequestAsync<StartVpnRequest, bool>("Start", request, cancellationToken);
    }

    public async Task<Result<bool, HelperError>> StopAsync(CancellationToken cancellationToken = default)
    {
        return await SendRequestAsync<object, bool>("Stop", null, cancellationToken);
    }

    public async Task<Result<HelperStatus, HelperError>> GetStatusAsync(CancellationToken cancellationToken = default)
    {
        return await SendRequestAsync<object, HelperStatus>("GetStatus", null, cancellationToken);
    }

    public async Task<Result<bool, HelperError>> PingAsync(CancellationToken cancellationToken = default)
    {
        return await SendRequestAsync<object, bool>("Ping", null, cancellationToken);
    }

    private async Task<Result<TResponse, HelperError>> SendRequestAsync<TRequest, TResponse>(string action, TRequest? payload, CancellationToken cancellationToken)
    {
        try
        {
            using var clientStream = new NamedPipeClientStream(".", PipeName, PipeDirection.InOut, PipeOptions.Asynchronous);
            
            // Retry policy for connecting to the pipe
            int retries = 5;
            int delayMs = 500;
            bool connected = false;

            while (retries > 0 && !cancellationToken.IsCancellationRequested)
            {
                try
                {
                    await clientStream.ConnectAsync(delayMs, cancellationToken);
                    connected = true;
                    break;
                }
                catch (TimeoutException)
                {
                    retries--;
                    if (retries > 0)
                    {
                        _logger.LogWarning("Timeout connecting to helper pipe. Retrying in {Delay}ms... ({Retries} left)", delayMs, retries);
                        delayMs *= 2; // Exponential backoff
                    }
                }
            }

            if (!connected)
            {
                _logger.LogError("Failed to connect to helper pipe after retries.");
                return Result<TResponse, HelperError>.Failure(new HelperError { Code = "TIMEOUT", Message = "Helper process is not responding." });
            }

            var requestMessage = new IpcMessage
            {
                Action = action,
                Payload = payload == null ? null : JsonSerializer.Serialize(payload, _jsonOptions)
            };

            var requestJson = JsonSerializer.Serialize(requestMessage, _jsonOptions);
            var requestBytes = Encoding.UTF8.GetBytes(requestJson);
            
            // Send length prefix (4 bytes)
            var lengthBytes = BitConverter.GetBytes(requestBytes.Length);
            await clientStream.WriteAsync(lengthBytes, cancellationToken);
            
            // Send payload
            await clientStream.WriteAsync(requestBytes, cancellationToken);

            // Read response length
            var responseLengthBytes = new byte[4];
            var read = await clientStream.ReadAsync(responseLengthBytes, cancellationToken);
            if (read < 4)
            {
                return Result<TResponse, HelperError>.Failure(new HelperError { Code = "IPC_ERROR", Message = "Failed to read response length from helper." });
            }

            var responseLength = BitConverter.ToInt32(responseLengthBytes, 0);
            
            // Protect against massive allocations if length is bogus
            if (responseLength > 10 * 1024 * 1024) 
                return Result<TResponse, HelperError>.Failure(new HelperError { Code = "IPC_ERROR", Message = "Response from helper is too large." });

            var responseBytes = new byte[responseLength];
            int totalRead = 0;
            while (totalRead < responseLength)
            {
                int bytesRead = await clientStream.ReadAsync(responseBytes.AsMemory(totalRead, responseLength - totalRead), cancellationToken);
                if (bytesRead == 0)
                    break;
                totalRead += bytesRead;
            }

            if (totalRead < responseLength)
            {
                return Result<TResponse, HelperError>.Failure(new HelperError { Code = "IPC_ERROR", Message = "Incomplete response from helper." });
            }

            var responseJson = Encoding.UTF8.GetString(responseBytes);
            var responseMessage = JsonSerializer.Deserialize<IpcResponse<TResponse>>(responseJson, _jsonOptions);

            if (responseMessage == null)
            {
                return Result<TResponse, HelperError>.Failure(new HelperError { Code = "IPC_ERROR", Message = "Failed to deserialize helper response." });
            }

            if (!responseMessage.Success)
            {
                return Result<TResponse, HelperError>.Failure(new HelperError { Code = responseMessage.ErrorCode ?? "HELPER_ERROR", Message = responseMessage.ErrorMessage ?? "Unknown helper error." });
            }

            return Result<TResponse, HelperError>.Success(responseMessage.Data!);
        }
        catch (TimeoutException)
        {
            _logger.LogWarning("Timeout connecting to helper process.");
            return Result<TResponse, HelperError>.Failure(new HelperError { Code = "TIMEOUT", Message = "Helper process is not responding or not running." });
        }
        catch (OperationCanceledException)
        {
            throw;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error communicating with helper process.");
            return Result<TResponse, HelperError>.Failure(new HelperError { Code = "IPC_ERROR", Message = $"Error communicating with helper:\n{ex.ToString()}", Exception = ex });
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
