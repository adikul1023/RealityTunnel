using System;
using System.Threading;
using System.Threading.Tasks;
using RealityTunnel.Models;

namespace RealityTunnel.Services;

public class VpnSessionManager
{
    private readonly XrayController _xrayController;
    private readonly ConfigurationProvider _configProvider;
    private int _retryCount;
    private CancellationTokenSource? _retryCts;
    private bool _userDisconnected;

    public event Action<string>? OnStateChanged;
    public event Action<bool>? OnConnectedChanged;
    public event Action<string>? OnRetryUpdate;
    
    public VpnSessionManager(XrayController xrayController, ConfigurationProvider configProvider)
    {
        _xrayController = xrayController;
        _configProvider = configProvider;
    }

    public bool IsRunning => _xrayController.IsRunning();

    public async Task StartSessionAsync()
    {
        _userDisconnected = false;
        _retryCount = 0;
        
        var profile = await _configProvider.GetVpnProfileAsync();

        if (profile != null && !string.IsNullOrEmpty(profile.ServerHost))
        {
            await ConnectInternalAsync(profile);
        }
        else
        {
            OnStateChanged?.Invoke("Failed (No Config)");
        }
    }

    private async Task ConnectInternalAsync(VpnProfile profile)
    {
        OnStateChanged?.Invoke("Connecting\u2026");
        if (_retryCount > 0)
        {
            OnRetryUpdate?.Invoke($"Retry #{_retryCount}");
        }

        try
        {
            await Task.Run(() => _xrayController.Start(profile));
            OnStateChanged?.Invoke("Connected");
            OnConnectedChanged?.Invoke(true);
            _retryCts = null;
            _retryCount = 0;
            OnRetryUpdate?.Invoke("OK");
        }
        catch (Exception ex)
        {
            try { System.IO.File.AppendAllText(System.IO.Path.Combine(XrayController.GetAppDirectory(), "runtime_trace.log"), $"\n[ConnectInternalAsync ERROR]\n{ex}\n"); } catch { }
            OnStateChanged?.Invoke("Failed");
            if (!_userDisconnected)
            {
                _ = AutoRetryAsync(profile);
            }
        }
    }

    private async Task AutoRetryAsync(VpnProfile profile)
    {
        _retryCts = new CancellationTokenSource();
        var token = _retryCts.Token;
        int[] delays = { 5, 10, 20, 30, 60 };

        while (!token.IsCancellationRequested)
        {
            int delay = delays[Math.Min(_retryCount, delays.Length - 1)];
            for (int i = delay; i > 0 && !token.IsCancellationRequested; i--)
            {
                OnRetryUpdate?.Invoke($"Retry in {i}s");
                await Task.Delay(1000, CancellationToken.None);
            }
            if (token.IsCancellationRequested) break;

            _retryCount++;
            await ConnectInternalAsync(profile);
            if (_xrayController.IsRunning()) break;
        }
    }

    public void StopSession()
    {
        _userDisconnected = true;
        _retryCts?.Cancel();
        _xrayController.Stop();
        OnStateChanged?.Invoke("Disconnected");
        OnConnectedChanged?.Invoke(false);
    }
}
