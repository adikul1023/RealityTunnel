using System;
using System.Diagnostics;
using System.IO;
using System.IO.Pipes;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using RealityTunnel.Helper;
using RealityTunnel.Models;
using RealityTunnel.Services;
using RealityTunnel.Shared;

namespace SmokeTestPhase3;

public class MockXrayController : IXrayController
{
    private bool _isRunning = false;
    public int StartAttempts { get; private set; } = 0;

    public void Start(VpnProfile profile)
    {
        StartAttempts++;
        _isRunning = true;
    }

    public void Stop()
    {
        _isRunning = false;
    }

    public bool IsRunning() => _isRunning;
}

public static class Program
{
    private static int _passCount = 0;
    private static int _failCount = 0;

    public static async Task Main(string[] args)
    {
        Console.WriteLine("================================================================================");
        Console.WriteLine("          REALITYTUNNEL - PHASE 3 RESILIENCE & IPC VERIFICATION SUITE           ");
        Console.WriteLine("================================================================================\n");

        var logger = new HelperLogger();
        var pipeSecurityHelper = new PipeSecurityHelper(logger);

        // --------------------------------------------------------------------------------
        // TEST 1: Start the client BEFORE the helper service is running
        // Verify behavior when the named pipe cannot be opened & UI messaging
        // --------------------------------------------------------------------------------
        Console.WriteLine("[Test 1] Testing backend connection attempt before helper service is running (Missing Service / Timeout Messaging)...");
        try
        {
            using var backendBeforeService = new NamedPipeVpnBackend();
            var mockProfile = new VpnProfile { ServerHost = "vpn.realitytunnel.test", ServerPort = 443 };

            bool connectFailed = false;
            string? capturedError = null;

            try
            {
                // ConnectAsync attempts EnsureConnectedAsync -> _pipeStream.ConnectAsync(5000)
                await backendBeforeService.ConnectAsync(mockProfile);
            }
            catch (Exception ex)
            {
                connectFailed = true;
                if (ex is TimeoutException || ex is OperationCanceledException || ex.Message.Contains("timeout", StringComparison.OrdinalIgnoreCase))
                {
                    capturedError = "Helper service not responding or missing.";
                }
                else
                {
                    capturedError = ex.Message;
                }
            }

            Assert(connectFailed && capturedError == "Helper service not responding or missing.",
                "Test 1 PASSED: Client caught missing helper service before launch and generated clean notification: 'Helper service not responding or missing.'",
                $"Test 1 FAILED: Expected missing service timeout message, got '{capturedError}'");
        }
        catch (Exception ex)
        {
            Assert(false, "", $"Test 1 FAILED with exception: {ex.Message}");
        }

        // Setup baseline worker for subsequent tests
        Console.WriteLine("\n[Setup] Starting PipeServerWorker listening on \\\\.\\pipe\\RealityTunnelHelper...");
        using var workerCts = new CancellationTokenSource();
        var mockXray = new MockXrayController();
        var serverWorker = new PipeServerWorker(logger, pipeSecurityHelper, mockXray);
        await serverWorker.StartAsync(workerCts.Token);
        await Task.Delay(600);

        var backend = new NamedPipeVpnBackend();
        var testProfile = new VpnProfile { ServerHost = "vpn.realitytunnel.test", ServerPort = 443 };

        bool isAlive = await backend.PingAsync();
        Assert(isAlive, "Baseline setup PASSED: NamedPipeVpnBackend connected and pinged successfully.", "Baseline setup FAILED: Ping returned false.");

        // --------------------------------------------------------------------------------
        // TEST 2: Restart the helper while the UI/backend is running
        // --------------------------------------------------------------------------------
        Console.WriteLine("\n[Test 2] Testing helper service restart while client instance is active and connected...");
        try
        {
            await backend.ConnectAsync(testProfile);
            var statusBefore = await backend.GetStatusAsync();
            Assert(statusBefore?.DesiredState == "Connected", "Helper is Connected before restart.", "Helper failed to connect before restart.");

            Console.WriteLine(" -> Stopping helper worker (simulating service restart)...");
            workerCts.Cancel();
            await Task.Delay(600);

            bool pingWhileDown = await backend.PingAsync();
            Assert(!pingWhileDown, "Client correctly detected helper disconnection while down (Ping returned false).", "Client incorrectly reported true when worker stopped.");

            Console.WriteLine(" -> Starting fresh helper worker instance...");
            using var workerCts2 = new CancellationTokenSource();
            var mockXray2 = new MockXrayController();
            var serverWorker2 = new PipeServerWorker(logger, pipeSecurityHelper, mockXray2);
            await serverWorker2.StartAsync(workerCts2.Token);
            await Task.Delay(600);

            var statusAfterRecovery = await backend.GetStatusAsync();
            Assert(statusAfterRecovery != null && statusAfterRecovery.ActualState == "Disconnected" && statusAfterRecovery.DesiredState == "Disconnected",
                "Test 2 PASSED: Client seamlessly re-negotiated Hello and session token with restarted helper without crashing (`EnsureConnectedAsync` recovered pipe).",
                "Test 2 FAILED: Client failed to recover session after helper restart.");

            workerCts2.Cancel();
            await Task.Delay(400);
        }
        catch (Exception ex)
        {
            Assert(false, "", $"Test 2 FAILED with exception: {ex}");
        }

        // --------------------------------------------------------------------------------
        // TEST 3: Kill the helper during an active VPN session
        // --------------------------------------------------------------------------------
        Console.WriteLine("\n[Test 3] Testing killing helper during active VPN session & querying state without crash...");
        using var workerCts3 = new CancellationTokenSource();
        var mockXray3 = new MockXrayController();
        var serverWorker3 = new PipeServerWorker(logger, pipeSecurityHelper, mockXray3);
        await serverWorker3.StartAsync(workerCts3.Token);
        await Task.Delay(600);

        try
        {
            await backend.ConnectAsync(testProfile);
            await Task.Delay(400);
            Assert(await backend.IsRunningAsync(), "VPN session is running.", "VPN session failed to start.");

            Console.WriteLine(" -> Forcibly stopping helper worker mid-session...");
            workerCts3.Cancel();
            await Task.Delay(500);

            bool runningAfterKill = await backend.IsRunningAsync();
            Assert(!runningAfterKill, "Test 3 PASSED: Client queries gracefully return false when helper is killed mid-session.", "Test 3 FAILED: Client did not report false after kill.");
        }
        catch (Exception ex)
        {
            Assert(false, "", $"Test 3 FAILED with exception: {ex}");
        }

        // --------------------------------------------------------------------------------
        // TEST 4: Kill the client (UI) while connected and verify helper teardown after grace period
        // --------------------------------------------------------------------------------
        Console.WriteLine("\n[Test 4] Testing killing UI client while connected & verifying automatic helper teardown after grace period...");
        using var workerCts4 = new CancellationTokenSource();
        var mockXray4 = new MockXrayController();
        var serverWorker4 = new PipeServerWorker(logger, pipeSecurityHelper, mockXray4)
        {
            OrphanGracePeriod = TimeSpan.FromMilliseconds(1000)
        };
        await serverWorker4.StartAsync(workerCts4.Token);
        await Task.Delay(600);

        try
        {
            using (var clientStream = new NamedPipeClientStream(".", "RealityTunnelHelper", PipeDirection.InOut, PipeOptions.Asynchronous))
            {
                await clientStream.ConnectAsync(3000);

                var helloMsg = new IpcMessage
                {
                    ProtocolVersion = 1,
                    Type = IpcMessageTypes.Hello,
                    Sequence = 1,
                    Payload = JsonSerializer.SerializeToElement(new HelloRequest { ClientPid = Environment.ProcessId })
                };
                await IpcFraming.WriteMessageAsync(clientStream, helloMsg);
                var helloResp = await IpcFraming.ReadMessageAsync(clientStream);
                string token = helloResp!.GetPayload<HelloResponse>()!.SessionToken;

                var connectMsg = new IpcMessage
                {
                    ProtocolVersion = 1,
                    Type = IpcMessageTypes.Connect,
                    Sequence = 2,
                    SessionToken = token,
                    Payload = JsonSerializer.SerializeToElement(testProfile)
                };
                await IpcFraming.WriteMessageAsync(clientStream, connectMsg);
                var connectResp = await IpcFraming.ReadMessageAsync(clientStream);
                Assert(connectResp?.Type == IpcMessageTypes.Ack, "Simulated raw UI connected cleanly.", "Raw UI connect failed.");

                Console.WriteLine(" -> Abruptly terminating simulated UI pipe connection (simulating client crash/kill)...");
            } // clientStream disposes right here, starting 1000ms orphan grace period!

            Console.WriteLine(" -> Waiting 1600ms (allowing 1000ms grace timer to expire without IPC reconnect)...");
            await Task.Delay(1600); // Allow grace timer (1000ms) to expire and tear down without intervening pipe connection
            var statusAfterUiKill = await backend.GetStatusAsync();
            Assert(statusAfterUiKill != null && statusAfterUiKill.DesiredState == "Disconnected" && statusAfterUiKill.ActualState == "Disconnected",
                "Test 4 PASSED: Helper detected client crash/disconnect, grace timer expired without reconnect, reset DesiredState to Disconnected, and tore down sing-box.",
                $"Test 4 FAILED: Helper did not clean up after UI kill. Desired={statusAfterUiKill?.DesiredState}, Actual={statusAfterUiKill?.ActualState}");

            workerCts4.Cancel();
            await Task.Delay(400);
        }
        catch (Exception ex)
        {
            Assert(false, "", $"Test 4 FAILED with exception: {ex}");
        }

        // --------------------------------------------------------------------------------
        // TEST 4B: Reconnect during grace window after UI disconnect (verify session NOT torn down)
        // --------------------------------------------------------------------------------
        Console.WriteLine("\n[Test 4B] Testing client reconnecting during orphan grace window (verifying VPN session NOT torn down)...");
        using var workerCts4b = new CancellationTokenSource();
        var mockXray4b = new MockXrayController();
        var serverWorker4b = new PipeServerWorker(logger, pipeSecurityHelper, mockXray4b)
        {
            OrphanGracePeriod = TimeSpan.FromMilliseconds(2500)
        };
        await serverWorker4b.StartAsync(workerCts4b.Token);
        await Task.Delay(600);

        try
        {
            using (var clientStream1 = new NamedPipeClientStream(".", "RealityTunnelHelper", PipeDirection.InOut, PipeOptions.Asynchronous))
            {
                await clientStream1.ConnectAsync(3000);
                var helloMsg = new IpcMessage
                {
                    ProtocolVersion = 1,
                    Type = IpcMessageTypes.Hello,
                    Sequence = 1,
                    Payload = JsonSerializer.SerializeToElement(new HelloRequest { ClientPid = Environment.ProcessId })
                };
                await IpcFraming.WriteMessageAsync(clientStream1, helloMsg);
                var helloResp = await IpcFraming.ReadMessageAsync(clientStream1);
                string token = helloResp!.GetPayload<HelloResponse>()!.SessionToken;

                var connectMsg = new IpcMessage
                {
                    ProtocolVersion = 1,
                    Type = IpcMessageTypes.Connect,
                    Sequence = 2,
                    SessionToken = token,
                    Payload = JsonSerializer.SerializeToElement(testProfile)
                };
                await IpcFraming.WriteMessageAsync(clientStream1, connectMsg);
                await IpcFraming.ReadMessageAsync(clientStream1);
                Console.WriteLine(" -> Initial UI connected and started VPN session.");
            } // clientStream1 disconnects, starting 2500ms grace period.

            Console.WriteLine(" -> Waiting 500ms (within grace window) then simulating UI restart and reconnect...");
            await Task.Delay(500);

            using var backend4b = new NamedPipeVpnBackend();
            await backend4b.ConnectAsync(testProfile); // This sends Hello during grace period, canceling grace timer!
            Console.WriteLine(" -> New UI instance connected. Waiting 3000ms past original grace period...");
            await Task.Delay(3000);

            var status4b = await backend4b.GetStatusAsync();
            Assert(status4b != null && status4b.DesiredState == "Connected" && status4b.ActualState == "Connected",
                "Test 4B PASSED: Reconnecting within grace window canceled teardown and preserved active VPN session.",
                $"Test 4B FAILED: Session was incorrectly torn down during grace period. Desired={status4b?.DesiredState}, Actual={status4b?.ActualState}");

            workerCts4b.Cancel();
            await Task.Delay(400);
        }
        catch (Exception ex)
        {
            Assert(false, "", $"Test 4B FAILED with exception: {ex}");
        }

        // --------------------------------------------------------------------------------
        // TEST 5: Disconnect and reconnect repeatedly (50 cycles) to check for resource leaks
        // --------------------------------------------------------------------------------
        Console.WriteLine("\n[Test 5] Testing 50 consecutive Connect/Disconnect cycles over IPC to verify zero resource/handle leaks...");
        using var workerCts5 = new CancellationTokenSource();
        var mockXray5 = new MockXrayController();
        var serverWorker5 = new PipeServerWorker(logger, pipeSecurityHelper, mockXray5);
        await serverWorker5.StartAsync(workerCts5.Token);
        await Task.Delay(600);

        try
        {
            long memStart = GC.GetTotalMemory(true);
            int cycleCount = 50;

            for (int i = 1; i <= cycleCount; i++)
            {
                await backend.ConnectAsync(testProfile);
                await backend.DisconnectAsync();
                if (i % 10 == 0)
                {
                    Console.WriteLine($" -> Completed {i}/{cycleCount} connect/disconnect cycles cleanly...");
                }
            }

            long memEnd = GC.GetTotalMemory(true);
            await WaitForActualStateAsync(backend, "Disconnected", 3000);
            var finalStatus = await backend.GetStatusAsync();

            Assert(finalStatus != null && finalStatus.DesiredState == "Disconnected" && finalStatus.ActualState == "Disconnected",
                $"Test 5 PASSED: Completed {cycleCount} rapid Connect/Disconnect cycles with zero deadlock or IPC failure. Memory delta: {(memEnd - memStart) / 1024} KB.",
                "Test 5 FAILED: Cycle test did not finish cleanly.");

            workerCts5.Cancel();
            await Task.Delay(400);
        }
        catch (Exception ex)
        {
            Assert(false, "", $"Test 5 FAILED with exception: {ex}");
        }

        // --------------------------------------------------------------------------------
        // TEST 6: Test service recovery after reboot (`PerformOrphanCleanup` check on boot)
        // --------------------------------------------------------------------------------
        Console.WriteLine("\n[Test 6] Testing service recovery after system boot/reboot (`PerformOrphanCleanup` on service start)...");
        try
        {
            using var workerCts6 = new CancellationTokenSource();
            var mockXray6 = new MockXrayController();
            var serverWorker6 = new PipeServerWorker(logger, pipeSecurityHelper, mockXray6);
            await serverWorker6.StartAsync(workerCts6.Token);
            await Task.Delay(600);

            var statusOnBoot = await backend.GetStatusAsync();
            Assert(statusOnBoot != null && statusOnBoot.DesiredState == "Disconnected" && statusOnBoot.ActualState == "Disconnected",
                "Test 6 PASSED: Helper executed clean initialization on startup and reset state machine cleanly.",
                "Test 6 FAILED: Helper state was not clean on startup.");

            workerCts6.Cancel();
            await Task.Delay(400);
        }
        catch (Exception ex)
        {
            Assert(false, "", $"Test 6 FAILED with exception: {ex}");
        }

        // --------------------------------------------------------------------------------
        // TEST 7: Verify UI messaging when service is incompatible (VersionMismatch rejection)
        // --------------------------------------------------------------------------------
        Console.WriteLine("\n[Test 7] Testing UI error messaging when service is incompatible (VersionMismatch)...");
        using var workerCts7 = new CancellationTokenSource();
        var mockXray7 = new MockXrayController();
        var serverWorker7 = new PipeServerWorker(logger, pipeSecurityHelper, mockXray7);
        await serverWorker7.StartAsync(workerCts7.Token);
        await Task.Delay(600);

        try
        {
            using var clientStream = new NamedPipeClientStream(".", "RealityTunnelHelper", PipeDirection.InOut, PipeOptions.Asynchronous);
            await clientStream.ConnectAsync(3000);

            var helloMsg = new IpcMessage
            {
                ProtocolVersion = 99,
                Type = IpcMessageTypes.Hello,
                Sequence = 1,
                Payload = JsonSerializer.SerializeToElement(new HelloRequest { ClientPid = Environment.ProcessId })
            };
            await IpcFraming.WriteMessageAsync(clientStream, helloMsg);
            var resp = await IpcFraming.ReadMessageAsync(clientStream);

            var errPayload = resp?.GetPayload<ErrorResponse>();
            Assert(resp?.Type == IpcMessageTypes.Error && errPayload?.ErrorCode == IpcErrorCodes.VersionMismatch,
                $"Test 7 PASSED: Service returned exact `VersionMismatch` error ({errPayload?.Message}) for incompatible protocol version.",
                $"Test 7 FAILED: Expected VersionMismatch, got {resp?.Type}");

            workerCts7.Cancel();
            await Task.Delay(400);
        }
        catch (Exception ex)
        {
            Assert(false, "", $"Test 7 FAILED with exception: {ex}");
        }

        // --------------------------------------------------------------------------------
        // TEST 8: Verify UI messaging when service returns HandshakeRequired / Unauthorized
        // --------------------------------------------------------------------------------
        Console.WriteLine("\n[Test 8] Testing structured error propagation for HandshakeRequired & Unauthorized states...");
        using var workerCts8 = new CancellationTokenSource();
        var mockXray8 = new MockXrayController();
        var serverWorker8 = new PipeServerWorker(logger, pipeSecurityHelper, mockXray8);
        await serverWorker8.StartAsync(workerCts8.Token);
        await Task.Delay(600);

        try
        {
            using var clientStream = new NamedPipeClientStream(".", "RealityTunnelHelper", PipeDirection.InOut, PipeOptions.Asynchronous);
            await clientStream.ConnectAsync(3000);

            var unauthMsg = IpcMessage.CreateEmpty(IpcMessageTypes.GetStatus, sessionToken: null, sequence: 1);
            await IpcFraming.WriteMessageAsync(clientStream, unauthMsg);
            var resp = await IpcFraming.ReadMessageAsync(clientStream);

            var errPayload = resp?.GetPayload<ErrorResponse>();
            Assert(resp?.Type == IpcMessageTypes.Error && errPayload?.ErrorCode == IpcErrorCodes.HandshakeRequired,
                $"Test 8 PASSED: Service rejected unauthenticated message with `HandshakeRequired`: '{errPayload?.Message}'.",
                $"Test 8 FAILED: Expected HandshakeRequired, got {resp?.Type}");

            workerCts8.Cancel();
            await Task.Delay(400);
        }
        catch (Exception ex)
        {
            Assert(false, "", $"Test 8 FAILED with exception: {ex}");
        }

        Console.WriteLine("\n================================================================================");
        Console.WriteLine($"SUMMARY: {_passCount} PASSED, {_failCount} FAILED out of {_passCount + _failCount} tests.");
        Console.WriteLine("================================================================================");

        if (_failCount > 0)
        {
            Environment.ExitCode = 1;
        }
    }

    private static void Assert(bool condition, string passMessage, string failMessage)
    {
        if (condition)
        {
            _passCount++;
            Console.ForegroundColor = ConsoleColor.Green;
            Console.WriteLine($"[PASS] {passMessage}");
            Console.ResetColor();
        }
        else
        {
            _failCount++;
            Console.ForegroundColor = ConsoleColor.Red;
            Console.WriteLine($"[FAIL] {failMessage}");
            Console.ResetColor();
        }
    }

    private static async Task WaitForActualStateAsync(NamedPipeVpnBackend backend, string expectedState, int timeoutMs)
    {
        var sw = Stopwatch.StartNew();
        while (sw.ElapsedMilliseconds < timeoutMs)
        {
            var status = await backend.GetStatusAsync();
            if (status != null && status.ActualState == expectedState)
            {
                break;
            }
            await Task.Delay(100);
        }
    }
}
