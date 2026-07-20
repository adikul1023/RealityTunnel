using System;
using System.IO.Pipes;
using System.Threading;
using System.Threading.Tasks;
using RealityTunnel.Helper;
using RealityTunnel.Models;
using RealityTunnel.Services;
using RealityTunnel.Shared;

namespace SmokeTestPhase2;

public class MockXrayController : IXrayController
{
    private bool _isRunning = false;
    public bool SimulateStartFailure { get; set; } = false;
    public string FailureMessage { get; set; } = "Simulated start failure";

    public void Start(VpnProfile profile)
    {
        if (SimulateStartFailure)
            throw new InvalidOperationException(FailureMessage);
        _isRunning = true;
    }

    public void Stop()
    {
        _isRunning = false;
    }

    public bool IsRunning() => _isRunning;
}

public class Program
{
    public static async Task Main(string[] args)
    {
        Console.WriteLine("================================================================================");
        Console.WriteLine("          REALITYTUNNEL - PHASE 2 INFRASTRUCTURE SMOKE TEST HARNESS              ");
        Console.WriteLine("================================================================================\n");

        int passed = 0;
        int total = 6;

        using var serverCts = new CancellationTokenSource();
        var logger = new HelperLogger();
        var pipeSecurityHelper = new PipeSecurityHelper(logger);
        var mockXray = new MockXrayController();
        var serverWorker = new PipeServerWorker(logger, pipeSecurityHelper, mockXray);

        Console.WriteLine("[Setup] Starting PipeServerWorker on background task listening on \\\\.\\pipe\\RealityTunnelHelper...");
        await serverWorker.StartAsync(serverCts.Token);
        await Task.Delay(500); // Allow pipe server to spin up and wait for connections

        try
        {
            // Test 1: Hello Handshake & Ping via NamedPipeVpnBackend
            Console.WriteLine("\n[Test 1] Testing Hello handshake and PingAsync over ACL'd Named Pipe...");
            using var backend = new NamedPipeVpnBackend();
            bool pingOk = await backend.PingAsync();
            if (pingOk)
            {
                Console.WriteLine("✔ Test 1 PASSED: Hello negotiation succeeded, session token established, Ping returned Ack.");
                passed++;
            }
            else
            {
                Console.WriteLine("✖ Test 1 FAILED: PingAsync returned false.");
            }

            // Test 2: GetStatus verification initial state
            Console.WriteLine("\n[Test 2] Testing GetStatusAsync initial state...");
            var status = await backend.GetStatusAsync();
            if (status != null && status.ActualState == "Disconnected" && status.DesiredState == "Disconnected" && !(await backend.IsRunningAsync()))
            {
                Console.WriteLine($"✔ Test 2 PASSED: GetStatus returned DesiredState={status.DesiredState}, ActualState={status.ActualState}, IsRunning=false.");
                passed++;
            }
            else
            {
                Console.WriteLine($"✖ Test 2 FAILED: GetStatus returned unexpected state: Desired={status?.DesiredState}, Actual={status?.ActualState}, IsRunning={await backend.IsRunningAsync()}");
            }

            // Test 3: Connect command & reconciliation loop state verification
            Console.WriteLine("\n[Test 3] Testing ConnectAsync and reconciliation loop transition to 'Connected'...");
            var profile = new VpnProfile
            {
                ServerHost = "vpn.realitytunnel.test",
                ServerPort = 443,
                Uuid = "12345678-1234-1234-1234-123456789012"
            };

            await backend.ConnectAsync(profile);

            GetStatusResponse? postConnectStatus = null;
            bool isRunningPostConnect = false;
            for (int i = 0; i < 20; i++)
            {
                postConnectStatus = await backend.GetStatusAsync();
                isRunningPostConnect = await backend.IsRunningAsync();
                if (postConnectStatus?.ActualState == "Connected" && isRunningPostConnect) break;
                await Task.Delay(100);
            }

            if (postConnectStatus?.ActualState == "Connected" && postConnectStatus?.DesiredState == "Connected" && isRunningPostConnect)
            {
                Console.WriteLine("✔ Test 3 PASSED: ConnectAsync succeeded, reconciliation loop transitioned ActualState to 'Connected'.");
                passed++;
            }
            else
            {
                Console.WriteLine($"✖ Test 3 FAILED: PostConnectActual={postConnectStatus?.ActualState}, Desired={postConnectStatus?.DesiredState}, IsRunning={isRunningPostConnect}");
            }

            // Test 4: Disconnect command & state verification
            Console.WriteLine("\n[Test 4] Testing DisconnectAsync and reconciliation loop transition to 'Disconnected'...");
            await backend.DisconnectAsync();

            GetStatusResponse? postDisconnectStatus = null;
            bool isRunningPostDisconnect = true;
            for (int i = 0; i < 20; i++)
            {
                postDisconnectStatus = await backend.GetStatusAsync();
                isRunningPostDisconnect = await backend.IsRunningAsync();
                if (postDisconnectStatus?.ActualState == "Disconnected" && !isRunningPostDisconnect) break;
                await Task.Delay(100);
            }

            if (postDisconnectStatus?.ActualState == "Disconnected" && postDisconnectStatus?.DesiredState == "Disconnected" && !isRunningPostDisconnect)
            {
                Console.WriteLine("✔ Test 4 PASSED: DisconnectAsync succeeded, reconciliation loop transitioned ActualState to 'Disconnected'.");
                passed++;
            }
            else
            {
                Console.WriteLine($"✖ Test 4 FAILED: PostDisconnectActual={postDisconnectStatus?.ActualState}, IsRunning={isRunningPostDisconnect}");
            }

            // Test 5: Verify hard gating on version negotiation / sequence rejection (unauthorized client behavior)
            Console.WriteLine("\n[Test 5] Testing hard gating: sending command without Hello handshake from raw pipe client...");
            using var rawClient = new NamedPipeClientStream(".", "RealityTunnelHelper", PipeDirection.InOut, PipeOptions.Asynchronous);
            await rawClient.ConnectAsync(3000);

            // Send Ping directly without Hello
            var unauthorizedPing = IpcMessage.CreateEmpty(IpcMessageTypes.Ping, sessionToken: null, sequence: 1);
            await IpcFraming.WriteMessageAsync(rawClient, unauthorizedPing);

            var rejectionResp = await IpcFraming.ReadMessageAsync(rawClient);
            if (rejectionResp != null && rejectionResp.Type == IpcMessageTypes.Error)
            {
                var err = rejectionResp.GetPayload<ErrorResponse>();
                if (err?.ErrorCode == IpcErrorCodes.HandshakeRequired)
                {
                    Console.WriteLine($"✔ Test 5 PASSED: Service rejected command before Hello handshake with error: '{err.ErrorCode}' ({err.Message}).");
                    passed++;
                }
                else
                {
                    Console.WriteLine($"✖ Test 5 FAILED: Received error code '{err?.ErrorCode}' instead of HandshakeRequired.");
                }
            }
            else
            {
                Console.WriteLine($"✖ Test 5 FAILED: Expected Error response, got '{rejectionResp?.Type ?? "null"}'.");
            }

            // Test 6: Reconciliation Loop Failure Handling & Error State Transition
            Console.WriteLine("\n[Test 6] Testing reconciliation loop handling of start failures and transition to 'Failed' state...");
            mockXray.SimulateStartFailure = true;
            mockXray.FailureMessage = "mock sing-box binary crashed on startup";
            await backend.ConnectAsync(profile);

            GetStatusResponse? failedStatus = null;
            for (int i = 0; i < 20; i++)
            {
                failedStatus = await backend.GetStatusAsync();
                if (failedStatus?.ActualState == "Failed") break;
                await Task.Delay(100);
            }

            if (failedStatus?.ActualState == "Failed" && failedStatus.LastError == "mock sing-box binary crashed on startup")
            {
                Console.WriteLine($"✔ Test 6 PASSED: Reconciliation loop caught start failure, set ActualState='Failed', and recorded LastError: '{failedStatus.LastError}'.");
                passed++;
            }
            else
            {
                Console.WriteLine($"✖ Test 6 FAILED: Expected ActualState='Failed' and LastError, got Actual='{failedStatus?.ActualState}', LastError='{failedStatus?.LastError}'");
            }
        }
        finally
        {
            Console.WriteLine("\n[Teardown] Stopping PipeServerWorker...");
            await serverWorker.StopAsync(CancellationToken.None);
        }

        Console.WriteLine("\n================================================================================");
        Console.WriteLine($"SUMMARY: {passed}/{total} tests passed.");
        Console.WriteLine("================================================================================");

        if (passed != total)
        {
            Environment.Exit(1);
        }
    }
}
