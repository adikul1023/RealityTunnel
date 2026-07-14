using System;
using System.Diagnostics;
using System.Threading;
using System.Threading.Tasks;
using RealityTunnel.Models;

namespace RealityTunnel.Services;

public sealed class DeviceHeartbeatService : IDisposable
{
    private readonly OracleApiClient _apiClient;
    private readonly TokenService _tokenService;
    private readonly SecureStorageService _storageService;
    private readonly ClientLogger _logger;
    private readonly Random _rand = new();

    private CancellationTokenSource? _cts;
    private Task? _loopTask;
    private Action? _onRevoked;
    private bool _isRunning;

    public DeviceHeartbeatService(
        OracleApiClient apiClient,
        TokenService tokenService,
        SecureStorageService storageService,
        ClientLogger logger)
    {
        _apiClient = apiClient;
        _tokenService = tokenService;
        _storageService = storageService;
        _logger = logger;
    }

    public bool IsRunning => _isRunning;

    /// <summary>
    /// Perform an immediate heartbeat presence check (e.g. on startup or restoration).
    /// Returns true if active or if network error occurred (fail-open for network resiliency).
    /// Returns false ONLY if the server explicitly reports active = false.
    /// </summary>
    public async Task<bool> CheckImmediateAsync(CancellationToken cancellationToken = default)
    {
        var tokens = _tokenService.CurrentTokens;
        var deviceGuid = _storageService.GetDeviceGuid();

        if (tokens == null || string.IsNullOrEmpty(tokens.AccessToken) || string.IsNullOrEmpty(deviceGuid))
        {
            return false;
        }

        var sw = Stopwatch.StartNew();
        try
        {
            var status = await _apiClient.CheckDeviceStatusAsync(tokens.AccessToken, deviceGuid, cancellationToken);
            sw.Stop();

            if (status != null)
            {
                if (status.Active)
                {
                    _logger.Log(LogLevel.INFO, "DEVICE_HEARTBEAT",
                        $"Status: Active | Server Time: {status.ServerTime:O} | Round Trip: {sw.ElapsedMilliseconds} ms");
                    return true;
                }
                else
                {
                    _logger.Log(LogLevel.WARN, "DEVICE_HEARTBEAT",
                        $"Status: Removed (Reason: {status.Reason ?? "DEVICE_REMOVED"}) | Round Trip: {sw.ElapsedMilliseconds} ms");
                    return false;
                }
            }

            _logger.Log(LogLevel.WARN, "DEVICE_HEARTBEAT", "Heartbeat status check returned empty response.");
            return true;
        }
        catch (Exception ex)
        {
            sw.Stop();
            _logger.Log(LogLevel.WARN, "DEVICE_HEARTBEAT", $"Network unavailable or error during immediate check ({sw.ElapsedMilliseconds} ms): {ex.Message}");
            return true;
        }
    }

    /// <summary>
    /// Start background heartbeat loop using PeriodicTimer and jitter.
    /// </summary>
    public void Start(Action onRevoked)
    {
        Stop();

        _onRevoked = onRevoked;
        _cts = new CancellationTokenSource();
        _isRunning = true;
        _logger.Log(LogLevel.INFO, "DEVICE_HEARTBEAT", "Heartbeat started");

        _loopTask = Task.Run(() => HeartbeatLoopAsync(_cts.Token));
    }

    public void Stop()
    {
        if (!_isRunning)
        {
            return;
        }

        _isRunning = false;
        try
        {
            _cts?.Cancel();
            _cts?.Dispose();
        }
        catch { }
        finally
        {
            _cts = null;
            _loopTask = null;
            _logger.Log(LogLevel.INFO, "DEVICE_HEARTBEAT", "Heartbeat stopped");
        }
    }

    private async Task HeartbeatLoopAsync(CancellationToken ct)
    {
        int baseIntervalSeconds = 60;
        int jitterRangeSeconds = 10;

        while (!ct.IsCancellationRequested && _isRunning)
        {
            // Calculate jitter: baseInterval ± jitterRangeSeconds
            int jitter = jitterRangeSeconds > 0 ? _rand.Next(-jitterRangeSeconds, jitterRangeSeconds + 1) : 0;
            int intervalSeconds = Math.Max(10, baseIntervalSeconds + jitter);

            using var timer = new PeriodicTimer(TimeSpan.FromSeconds(intervalSeconds));
            try
            {
                if (await timer.WaitForNextTickAsync(ct))
                {
                    var tokens = _tokenService.CurrentTokens;
                    var deviceGuid = _storageService.GetDeviceGuid();

                    if (tokens == null || string.IsNullOrEmpty(tokens.AccessToken) || string.IsNullOrEmpty(deviceGuid))
                    {
                        continue;
                    }

                    var sw = Stopwatch.StartNew();
                    try
                    {
                        var status = await _apiClient.CheckDeviceStatusAsync(tokens.AccessToken, deviceGuid, ct);
                        sw.Stop();

                        if (status != null)
                        {
                            if (status.HeartbeatInterval > 0)
                            {
                                baseIntervalSeconds = status.HeartbeatInterval;
                            }
                            if (status.HeartbeatJitter >= 0)
                            {
                                jitterRangeSeconds = status.HeartbeatJitter;
                            }

                            if (status.Active)
                            {
                                _logger.Log(LogLevel.INFO, "DEVICE_HEARTBEAT",
                                    $"Status: Active | Server Time: {status.ServerTime:O} | Round Trip: {sw.ElapsedMilliseconds} ms");
                            }
                            else
                            {
                                _logger.Log(LogLevel.WARN, "DEVICE_HEARTBEAT",
                                    $"Device removed | Status: Removed (Reason: {status.Reason ?? "DEVICE_REMOVED"}) | Round Trip: {sw.ElapsedMilliseconds} ms");
                                InvokeRevoked();
                                break;
                            }
                        }
                    }
                    catch (OperationCanceledException)
                    {
                        break;
                    }
                    catch (Exception ex)
                    {
                        sw.Stop();
                        _logger.Log(LogLevel.WARN, "DEVICE_HEARTBEAT", $"Network unavailable. Retry next minute. ({ex.Message})");
                    }
                }
            }
            catch (OperationCanceledException)
            {
                break;
            }
        }
    }

    private void InvokeRevoked()
    {
        _isRunning = false;
        var cb = _onRevoked;
        cb?.Invoke();
    }

    public void Dispose()
    {
        Stop();
    }
}
