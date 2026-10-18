using System;
using System.IO.Pipes;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging.Abstractions;
using OverREALITY.Helper;
using OverREALITY.Infrastructure.Services;
using OverREALITY.Shared.Api.Configuration;
using OverREALITY.Shared.Api.VpnRuntime;
using Xunit;

namespace OverREALITY.Tests.Helper;

public class IpcServerTests
{
    [Fact]
    public async Task Start_HandlerThrows_ReturnsStructuredErrorResponse()
    {
        using var cts = new CancellationTokenSource();
        var server = new IpcServer(NullLogger<IpcServer>.Instance);
        var expectedError = "sing-box startup failed: configure tun interface: Access is denied.";

        server.OnStartRequested = (req) =>
        {
            throw new Exception(expectedError);
        };

        var serverTask = Task.Run(() => server.StartListeningAsync(cts.Token));
        await Task.Delay(100);

        var client = new HelperClient(NullLogger<HelperClient>.Instance);
        var startReq = new StartVpnRequest
        {
            Config = new VPNConfig
            {
                SchemaVersion = 1,
                JsonConfig = "{\"test\":true}"
            }
        };

        var result = await client.StartAsync(startReq, CancellationToken.None);

        Assert.False(result.IsSuccess);
        Assert.NotNull(result.Error);
        Assert.Contains("configure tun interface: Access is denied", result.Error.Message);
        Assert.Equal("HANDLER_ERROR", result.Error.Code);

        cts.Cancel();
        try { await serverTask; } catch { }
    }

    [Fact]
    public async Task Ping_ReturnsSuccess()
    {
        using var cts = new CancellationTokenSource();
        var server = new IpcServer(NullLogger<IpcServer>.Instance);
        var serverTask = Task.Run(() => server.StartListeningAsync(cts.Token));
        await Task.Delay(100);

        var client = new HelperClient(NullLogger<HelperClient>.Instance);
        var result = await client.PingAsync(CancellationToken.None);

        Assert.True(result.IsSuccess);
        Assert.True(result.Value);

        cts.Cancel();
        try { await serverTask; } catch { }
    }

    [Fact]
    public async Task GetStatus_ReturnsCurrentStatus()
    {
        using var cts = new CancellationTokenSource();
        var server = new IpcServer(NullLogger<IpcServer>.Instance);
        server.OnStatusRequested = () => HelperStatus.Running;

        var serverTask = Task.Run(() => server.StartListeningAsync(cts.Token));
        await Task.Delay(100);

        var client = new HelperClient(NullLogger<HelperClient>.Instance);
        var result = await client.GetStatusAsync(CancellationToken.None);

        Assert.True(result.IsSuccess);
        Assert.Equal(HelperStatus.Running, result.Value);

        cts.Cancel();
        try { await serverTask; } catch { }
    }

    [Fact]
    public async Task Stop_ReturnsSuccess()
    {
        using var cts = new CancellationTokenSource();
        var server = new IpcServer(NullLogger<IpcServer>.Instance);
        server.OnStopRequested = () => Task.FromResult(true);

        var serverTask = Task.Run(() => server.StartListeningAsync(cts.Token));
        await Task.Delay(100);

        var client = new HelperClient(NullLogger<HelperClient>.Instance);
        var result = await client.StopAsync(CancellationToken.None);

        Assert.True(result.IsSuccess);
        Assert.True(result.Value);

        cts.Cancel();
        try { await serverTask; } catch { }
    }

    [Fact]
    public async Task MalformedJson_ReturnsDeserializationError()
    {
        using var cts = new CancellationTokenSource();
        var server = new IpcServer(NullLogger<IpcServer>.Instance);
        var serverTask = Task.Run(() => server.StartListeningAsync(cts.Token));
        await Task.Delay(100);

        using var clientStream = new NamedPipeClientStream(".", "OverREALITY_Helper_Pipe_v5", PipeDirection.InOut, PipeOptions.Asynchronous);
        await clientStream.ConnectAsync(1000);

        var badJson = "{ invalid json here";
        var badJsonBytes = Encoding.UTF8.GetBytes(badJson);
        await clientStream.WriteAsync(BitConverter.GetBytes(badJsonBytes.Length));
        await clientStream.WriteAsync(badJsonBytes);
        await clientStream.FlushAsync();

        var lenBytes = new byte[4];
        await clientStream.ReadExactlyAsync(lenBytes);
        int respLen = BitConverter.ToInt32(lenBytes, 0);
        var respBytes = new byte[respLen];
        await clientStream.ReadExactlyAsync(respBytes);
        var respJson = Encoding.UTF8.GetString(respBytes);

        Assert.Contains("DESERIALIZATION_ERROR", respJson);

        cts.Cancel();
        try { await serverTask; } catch { }
    }

    [Fact]
    public async Task InvalidLengthPrefix_ReturnsInvalidLengthError()
    {
        using var cts = new CancellationTokenSource();
        var server = new IpcServer(NullLogger<IpcServer>.Instance);
        var serverTask = Task.Run(() => server.StartListeningAsync(cts.Token));
        await Task.Delay(100);

        using var clientStream = new NamedPipeClientStream(".", "OverREALITY_Helper_Pipe_v5", PipeDirection.InOut, PipeOptions.Asynchronous);
        await clientStream.ConnectAsync(1000);

        // Send invalid length of 0
        await clientStream.WriteAsync(BitConverter.GetBytes(0));
        await clientStream.FlushAsync();

        var lenBytes = new byte[4];
        await clientStream.ReadExactlyAsync(lenBytes);
        int respLen = BitConverter.ToInt32(lenBytes, 0);
        var respBytes = new byte[respLen];
        await clientStream.ReadExactlyAsync(respBytes);
        var respJson = Encoding.UTF8.GetString(respBytes);

        Assert.Contains("INVALID_LENGTH", respJson);

        cts.Cancel();
        try { await serverTask; } catch { }
    }
}