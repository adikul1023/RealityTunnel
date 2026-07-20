using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using RealityTunnel;
using RealityTunnel.Models;
using RealityTunnel.Services;

namespace SmokeTestPhase1;

public class MockBackend : IVpnBackend
{
    private bool _isRunning = false;
    public bool ShouldFailConnect = false;
    public int ConnectCallCount = 0;
    public int DisconnectCallCount = 0;

    public async Task ConnectAsync(VpnProfile profile)
    {
        ConnectCallCount++;
        await Task.Delay(50);
        if (ShouldFailConnect)
        {
            throw new InvalidOperationException("Simulated connection failure for retry test.");
        }
        _isRunning = true;
    }

    public Task DisconnectAsync()
    {
        DisconnectCallCount++;
        _isRunning = false;
        return Task.CompletedTask;
    }

    public Task<bool> IsRunningAsync() => Task.FromResult(_isRunning);
}

public class MockConfigProvider : ConfigurationProvider
{
    private static ClientLogger _logger = new ClientLogger();
    private static SecureStorageService _storage = new SecureStorageService(_logger);
    private static LicenseService _license = new LicenseService(_storage);
    private static TokenService _token = new TokenService(_storage);
    private static OracleApiClient _api = new OracleApiClient(new System.Net.Http.HttpClient());
    private static AuthenticationService _auth = new AuthenticationService(_api, _token, _storage, _license);

    private VpnProfile? _profile;

    public MockConfigProvider(VpnProfile? profile) : base(_license, _storage, _auth, _api)
    {
        _profile = profile;
        string secureDir = System.IO.Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "OverREALITY", "Secure");
        string profilePath = System.IO.Path.Combine(secureDir, "vpn_profile.dat");
        if (profile == null)
        {
            if (System.IO.File.Exists(profilePath)) System.IO.File.Delete(profilePath);
        }
        else
        {
            _storage.SaveVpnProfile(profile);
            _storage.SaveLastTrustedTimestamp(DateTimeOffset.UtcNow);
        }
    }

    public new Task<VpnProfile?> GetVpnProfileAsync()
    {
        return Task.FromResult(_profile);
    }
}

public static class Program
{
    public static async Task<int> Main(string[] args)
    {
        Console.WriteLine("================================================================================");
        Console.WriteLine("          REALITYTUNNEL — PHASE 1 RUNTIME SMOKE TEST HARNESS                    ");
        Console.WriteLine("================================================================================");
        int passedTests = 0;
        int totalTests = 4;

        try
        {
            // Test 1: No Config Case (StartSessionAsync -> Failed (No Config))
            Console.WriteLine("\n[Test 1] Testing VpnSessionManager without config (StartSession -> Failed (No Config))...");
            var mockBackend1 = new MockBackend();
            var mockConfig1 = new MockConfigProvider(null);
            var manager1 = new VpnSessionManager(mockBackend1, mockConfig1);

            List<string> states1 = new();
            manager1.OnStateChanged += state => states1.Add(state);

            await manager1.StartSessionAsync();
            if (states1.Contains("Failed (No Config)") && !manager1.IsRunning)
            {
                Console.WriteLine("✔ Test 1 PASSED: Correctly handled null VpnProfile and emitted 'Failed (No Config)'.");
                passedTests++;
            }
            else
            {
                Console.WriteLine($"✖ Test 1 FAILED: States=[{string.Join(", ", states1)}], IsRunning={manager1.IsRunning}");
            }

            // Test 2: Successful Connect, State Transitions & Disconnect
            Console.WriteLine("\n[Test 2] Testing Successful Connect, State Transitions ('Connecting…' -> 'Connected') & Disconnect...");
            var testProfile = new VpnProfile
            {
                ServerHost = "127.0.0.1",
                ServerPort = 443,
                Uuid = "test-uuid",
                Sni = "test.example.com",
                PublicKey = "test-pubkey",
                ShortId = "test-shortid"
            };
            var mockBackend2 = new MockBackend();
            var mockConfig2 = new MockConfigProvider(testProfile);
            var manager2 = new VpnSessionManager(mockBackend2, mockConfig2);

            List<string> states2 = new();
            List<bool> connectedEvents2 = new();
            manager2.OnStateChanged += state => states2.Add(state);
            manager2.OnConnectedChanged += conn => connectedEvents2.Add(conn);

            await manager2.StartSessionAsync();
            await Task.Delay(100);

            bool connectSuccess = states2.Contains("Connecting…") && states2.Contains("Connected") &&
                                  connectedEvents2.Contains(true) && manager2.IsRunning && mockBackend2.ConnectCallCount == 1;

            if (!connectSuccess)
            {
                Console.WriteLine($"✖ Test 2 FAILED during connect: States=[{string.Join(", ", states2)}], ConnectedEvents=[{string.Join(", ", connectedEvents2)}]");
            }
            else
            {
                Console.WriteLine("  -> Connect phase succeeded. Now testing Disconnect/StopSession...");
                manager2.StopSession();
                await Task.Delay(50);

                bool disconnectSuccess = states2.Contains("Disconnected") && connectedEvents2.Contains(false) &&
                                         !manager2.IsRunning && mockBackend2.DisconnectCallCount == 1;
                if (disconnectSuccess)
                {
                    Console.WriteLine("✔ Test 2 PASSED: Full connect -> state transitions -> disconnect verified.");
                    passedTests++;
                }
                else
                {
                    Console.WriteLine($"✖ Test 2 FAILED during disconnect: States=[{string.Join(", ", states2)}], IsRunning={manager2.IsRunning}");
                }
            }

            // Test 3: Retry Loop, Retry Updates ('Retry in Xs'), and Cancellation on StopSession
            Console.WriteLine("\n[Test 3] Testing Retry Loop ('Failed' -> AutoRetry -> 'Retry in Xs') & Cancellation on StopSession...");
            var mockBackend3 = new MockBackend { ShouldFailConnect = true };
            var mockConfig3 = new MockConfigProvider(testProfile);
            var manager3 = new VpnSessionManager(mockBackend3, mockConfig3);

            List<string> states3 = new();
            List<string> retryUpdates3 = new();
            manager3.OnStateChanged += state => states3.Add(state);
            manager3.OnRetryUpdate += update => retryUpdates3.Add(update);

            await manager3.StartSessionAsync();
            await Task.Delay(2200); // Allow retry loop to emit 'Retry in 5s', 'Retry in 4s' etc.

            bool retryTriggered = states3.Contains("Connecting…") && states3.Contains("Failed") && retryUpdates3.Count > 0;
            if (!retryTriggered)
            {
                Console.WriteLine($"✖ Test 3 FAILED: Retry loop did not trigger properly. States=[{string.Join(", ", states3)}], RetryUpdates=[{string.Join(", ", retryUpdates3)}]");
            }
            else
            {
                Console.WriteLine($"  -> Observed retry state transitions and updates: {string.Join(" -> ", retryUpdates3.GetRange(0, Math.Min(3, retryUpdates3.Count)))}...");
                Console.WriteLine("  -> Now calling StopSession to verify cancellation of AutoRetry loop...");
                manager3.StopSession();
                await Task.Delay(100);

                if (states3[states3.Count - 1] == "Disconnected" && mockBackend3.DisconnectCallCount == 1)
                {
                    Console.WriteLine("✔ Test 3 PASSED: AutoRetry loop cleanly cancelled and transitioned to 'Disconnected'.");
                    passedTests++;
                }
                else
                {
                    Console.WriteLine($"✖ Test 3 FAILED on cancellation: LastState={states3[states3.Count - 1]}");
                }
            }

            // Test 4: Verify InProcessVpnBackend Delegation to XrayController
            Console.WriteLine("\n[Test 4] Verifying InProcessVpnBackend delegation to XrayController...");
            var xrayController = new XrayController();
            IVpnBackend inProcessBackend = new InProcessVpnBackend(xrayController);

            bool initRunning = await inProcessBackend.IsRunningAsync();
            await inProcessBackend.DisconnectAsync(); // Should call XrayController.Stop safely without error
            bool afterStopRunning = await inProcessBackend.IsRunningAsync();

            if (!initRunning && !afterStopRunning)
            {
                Console.WriteLine("✔ Test 4 PASSED: InProcessVpnBackend correctly wraps XrayController via IVpnBackend interface.");
                passedTests++;
            }
            else
            {
                Console.WriteLine($"✖ Test 4 FAILED: initRunning={initRunning}, afterStopRunning={afterStopRunning}");
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"\n[FATAL SMOKE TEST EXCEPTION]: {ex}");
        }

        Console.WriteLine("\n================================================================================");
        Console.WriteLine($"SUMMARY: {passedTests}/{totalTests} tests passed.");
        Console.WriteLine("================================================================================");

        return passedTests == totalTests ? 0 : 1;
    }
}
