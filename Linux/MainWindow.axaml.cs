using Avalonia.Controls;
using Avalonia.Media;
using Avalonia.Threading;
using OverREALITY.Core;
using System;
using System.Net.Http;
using System.Threading;
using System.Threading.Tasks;

namespace OverREALITY.Linux;

public partial class MainWindow : Window
{
    private readonly VpnController    _vpn      = new();
    private readonly AppSettings      _settings = AppSettings.Load();
    private readonly DispatcherTimer  _timer    = new() { Interval = TimeSpan.FromSeconds(1) };
    private readonly HttpClient       _http     = new() { Timeout = TimeSpan.FromSeconds(10) };
    private CancellationTokenSource?  _retryCts;
    private DateTime                  _connectedAt;
    private bool                      _connecting;

    private static readonly int[] RetryDelays = { 5, 10, 20, 30, 60 };

    public MainWindow()
    {
        InitializeComponent();
        ServerIpBox.Text = _settings.ServerIp;
        _timer.Tick += (_, _) => UpdateTimer();

        if (!string.IsNullOrWhiteSpace(_settings.ServerIp))
            _ = ConnectAsync(_settings.ServerIp);
    }

    // ── Connect ─────────────────────────────────────────────────────────
    private async void OnConnect(object? sender, Avalonia.Interactivity.RoutedEventArgs e)
    {
        string ip = ServerIpBox.Text?.Trim() ?? "";
        if (string.IsNullOrEmpty(ip)) return;
        _settings.ServerIp = ip;
        _settings.Save();
        await ConnectAsync(ip);
    }

    private async Task ConnectAsync(string ip)
    {
        _retryCts?.Cancel();
        _retryCts = new CancellationTokenSource();
        await AutoRetryAsync(ip, _retryCts.Token);
    }

    private async Task AutoRetryAsync(string ip, CancellationToken ct)
    {
        int attempt = 0;
        while (!ct.IsCancellationRequested)
        {
            SetState("Connecting…", "#FFA500", "#3A2800");
            _connecting = true;
            try
            {
                await Task.Run(() => _vpn.Start(ip), ct);
                _connectedAt = DateTime.Now;
                _timer.Start();
                SetState("Connected", "#00DD88", "#003322");
                RetryLabel.Text = "";
                _connecting = false;
                _ = FetchExitIpAsync();
                return;
            }
            catch (OperationCanceledException) { return; }
            catch (Exception ex)
            {
                SetState("Failed", "#FF4444", "#330000");
                int delay = RetryDelays[Math.Min(attempt, RetryDelays.Length - 1)];
                RetryLabel.Text = $"Retry in {delay}s — {ex.Message.Split('\n')[0]}";
                attempt++;
                try { await Task.Delay(TimeSpan.FromSeconds(delay), ct); } catch { return; }
            }
        }
    }

    // ── Disconnect ───────────────────────────────────────────────────────
    private async void OnDisconnect(object? sender, Avalonia.Interactivity.RoutedEventArgs e)
    {
        _retryCts?.Cancel();
        _timer.Stop();
        TimerLabel.Text  = "00:00:00";
        ExitIpLabel.Text = "";
        RetryLabel.Text  = "";
        SetState("Disconnecting…", "#888888", "#1A1A2A");
        await Task.Run(() => _vpn.Stop());
        SetState("Disconnected", "#888888", "#1A1A2A");
    }

    // ── Helpers ──────────────────────────────────────────────────────────
    private void SetState(string status, string orbColor, string glowColor)
    {
        Dispatcher.UIThread.Post(() =>
        {
            StatusLabel.Text        = status;
            Orb.Fill                = new SolidColorBrush(Avalonia.Media.Color.Parse(orbColor));
            OrbGlow.Fill            = new SolidColorBrush(Avalonia.Media.Color.Parse(glowColor));
            ConnectBtn.IsEnabled    = !_vpn.IsRunning() && !_connecting;
            DisconnectBtn.IsEnabled = _vpn.IsRunning() || _connecting;
        });
    }

    private void UpdateTimer()
    {
        if (_vpn.IsRunning())
        {
            var elapsed = DateTime.Now - _connectedAt;
            TimerLabel.Text = elapsed.ToString(@"hh\:mm\:ss");
        }
    }

    private async Task FetchExitIpAsync()
    {
        try
        {
            string ip = (await _http.GetStringAsync("https://ifconfig.me/ip")).Trim();
            Dispatcher.UIThread.Post(() => ExitIpLabel.Text = $"Exit: {ip}");
        }
        catch { }
    }
}
