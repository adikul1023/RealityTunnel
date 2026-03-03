using Microsoft.UI;
using Microsoft.UI.Windowing;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Input;
using Microsoft.UI.Xaml.Media;
using OverREALITY.Core;
using System;
using System.Net.Http;
using System.Runtime.InteropServices;
using System.Threading;
using System.Threading.Tasks;
using Windows.Graphics;
using Windows.UI;

namespace RealityTunnel;

public sealed partial class MainWindow : Window
{
    // Win32 for window drag
    [DllImport("user32.dll")] private static extern bool ReleaseCapture();
    [DllImport("user32.dll")] private static extern IntPtr PostMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);
    private const uint WM_NCLBUTTONDOWN = 0x00A1;
    private const int  HTCAPTION = 2;

    private readonly XrayController _xrayController = new();
    private readonly AppSettings _settings = AppSettings.Load();
    private readonly TrayIcon _tray;
    private readonly DispatcherTimer _timer = new();
    private readonly HttpClient _http = new() { Timeout = TimeSpan.FromSeconds(8) };

    private DateTime _connectedAt;
    private int _retryCount;
    private bool _userDisconnected;
    private CancellationTokenSource? _retryCts;

    private static readonly Color Green  = Color.FromArgb(255, 50,  205, 100);
    private static readonly Color Gray   = Color.FromArgb(255, 120, 120, 120);
    private static readonly Color Orange = Color.FromArgb(255, 255, 165,   0);

    public MainWindow()
    {
        InitializeComponent();
        _tray = new TrayIcon(this);

        // Compact floating window — no title bar chrome, always on top
        var appWin = AppWindow;
        appWin.Resize(new SizeInt32(260, 420));
        if (appWin.Presenter is OverlappedPresenter p)
        {
            p.IsResizable    = false;
            p.IsMaximizable  = false;
            p.IsAlwaysOnTop  = true;
        }
        ExtendsContentIntoTitleBar = true;

        // Set taskbar / title-bar icon
        string? exeDir = System.IO.Path.GetDirectoryName(Environment.ProcessPath);
        string iconPath = System.IO.Path.Combine(exeDir ?? AppContext.BaseDirectory, "app.ico");
        if (System.IO.File.Exists(iconPath))
            AppWindow.SetIcon(iconPath);

        _timer.Tick += Timer_Tick;

        ServerIpTextBox.Text = _settings.ServerIp;
        this.Closed += OnClosed;

        if (!string.IsNullOrWhiteSpace(_settings.ServerIp))
            _ = ConnectAsync(_settings.ServerIp);
    }

    // ── Connect / Disconnect ─────────────────────────────────────────────────

    private async Task ConnectAsync(string ip)
    {
        SetState("Connecting\u2026", Orange, "");
        RetryLabel.Text  = _retryCount > 0 ? $"Retry #{_retryCount}" : "\u2014";
        ExitIpLabel.Text = "\u2014";

        try
        {
            await Task.Run(() => _xrayController.Start(ip));
            _connectedAt = DateTime.Now;
            _timer.Start();
            SetState("Connected", Green, "");
            _tray.SetConnected(true);
            _retryCts   = null;
            _retryCount = 0;
            RetryLabel.Text = "OK";
            _ = FetchExitIpAsync();
        }
        catch
        {
            SetState("Failed", Gray, "");
            if (!_userDisconnected)
                _ = AutoRetryAsync(ip);
        }
    }

    private async Task AutoRetryAsync(string ip)
    {
        _retryCts = new CancellationTokenSource();
        var token  = _retryCts.Token;
        int[] delays = { 5, 10, 20, 30, 60 };

        while (!token.IsCancellationRequested)
        {
            int delay = delays[Math.Min(_retryCount, delays.Length - 1)];
            for (int i = delay; i > 0 && !token.IsCancellationRequested; i--)
            {
                RetryLabel.Text = $"Retry in {i}s";
                await Task.Delay(1000, CancellationToken.None);
            }
            if (token.IsCancellationRequested) break;

            _retryCount++;
            await ConnectAsync(ip);
            if (_xrayController.IsRunning()) break;
        }
    }

    private async void ConnectButton_Click(object sender, RoutedEventArgs e)
    {
        string ip = ServerIpTextBox.Text.Trim();
        if (string.IsNullOrWhiteSpace(ip)) { await ShowError("Enter a server IP."); return; }

        _userDisconnected = false;
        _retryCount = 0;
        _settings.ServerIp = ip;
        _settings.Save();
        await ConnectAsync(ip);
    }

    private void DisconnectButton_Click(object sender, RoutedEventArgs e) => Disconnect();

    internal void DisconnectFromTray() => Disconnect();

    private void Disconnect()
    {
        _userDisconnected = true;
        _retryCts?.Cancel();
        _timer.Stop();
        _xrayController.Stop();
        SetState("Disconnected", Gray, "");
        ExitIpLabel.Text = "\u2014";
        RetryLabel.Text  = "\u2014";
        _tray.SetConnected(false);
    }

    // ── UI helpers ───────────────────────────────────────────────────────────

    private void SetState(string label, Color orb, string timer)
    {
        StatusLabel.Text = label;
        TimerLabel.Text  = timer;
        StatusIcon.Foreground = new SolidColorBrush(orb);
        StatusOrbGlow.Fill    = new SolidColorBrush(Color.FromArgb(60, orb.R, orb.G, orb.B));

        bool connected = _xrayController.IsRunning();
        ConnectButton.IsEnabled    = !connected;
        DisconnectButton.IsEnabled =  connected;
        ServerIpTextBox.IsEnabled  = !connected;
    }

    private void Timer_Tick(object? sender, object e)
        => TimerLabel.Text = (DateTime.Now - _connectedAt).ToString(@"hh\:mm\:ss");

    private async Task FetchExitIpAsync()
    {
        try
        {
            ExitIpLabel.Text = "\u2026";
            ExitIpLabel.Text = (await _http.GetStringAsync("https://ifconfig.me/ip")).Trim();
        }
        catch { ExitIpLabel.Text = "?"; }
    }

    private void TitleBar_PointerPressed(object sender, PointerRoutedEventArgs e)
    {
        var hWnd = WinRT.Interop.WindowNative.GetWindowHandle(this);
        ReleaseCapture();
        PostMessage(hWnd, WM_NCLBUTTONDOWN, (IntPtr)HTCAPTION, IntPtr.Zero);
    }

    private void MinimiseButton_Click(object sender, RoutedEventArgs e)
    {
        AppWindow.Hide();
        _tray.ShowBalloon("OverREALITY running in tray");
    }

    private void OnClosed(object sender, WindowEventArgs args)
    {
        args.Handled = true;
        AppWindow.Hide();
        _tray.ShowBalloon("OverREALITY running in tray");
    }

    internal void ShowFromTray()
    {
        AppWindow.Show();
        AppWindow.SetPresenter(AppWindowPresenterKind.Overlapped);
        if (AppWindow.Presenter is OverlappedPresenter p)
        {
            p.IsResizable   = false;
            p.IsMaximizable = false;
            p.IsAlwaysOnTop = true;
        }
    }

    internal void ExitApp()
    {
        _userDisconnected = true;
        _retryCts?.Cancel();
        _xrayController.Stop();
        _tray.Dispose();
        Application.Current.Exit();
    }

    private async Task ShowError(string msg)
    {
        var dlg = new ContentDialog
        {
            Title = "Error", Content = msg, CloseButtonText = "OK",
            XamlRoot = Content.XamlRoot
        };
        await dlg.ShowAsync();
    }
}

