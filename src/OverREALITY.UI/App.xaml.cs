using System;
using System.ComponentModel;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using Hardcodet.Wpf.TaskbarNotification;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using OverREALITY.Configuration;
using OverREALITY.Core;
using OverREALITY.Infrastructure;
using OverREALITY.Shared.Interfaces;
using OverREALITY.Shared.Logging;
using OverREALITY.UI.ViewModels;
using OverREALITY.UI.Views;
using OverREALITY.UI.Services;

namespace OverREALITY.UI;

public partial class App : Application
{
    private readonly IHost _host;
    private TaskbarIcon? _notifyIcon;
    private bool _isExiting;

    public App()
    {
        _host = Host.CreateDefaultBuilder()
            .ConfigureLogging((context, logging) =>
            {
                logging.ClearProviders();
                logging.AddConsole();
                try
                {
                    var logDir = System.IO.Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "OverREALITY", "logs");
                    if (!System.IO.Directory.Exists(logDir))
                    {
                        System.IO.Directory.CreateDirectory(logDir);
                    }
                    var logFile = System.IO.Path.Combine(logDir, "ui.log");
                    logging.AddProvider(new FileLoggerProvider(logFile));
                }
                catch { }
            })
            .ConfigureServices((context, services) =>
            {
                // Register backend
                services.AddConfigurationServices();
                services.AddInfrastructureServices();
                services.AddCoreServices();

                // UI Services
                services.AddSingleton<INavigationService, NavigationService>();
                services.AddSingleton<IUiDispatcher, WpfUiDispatcher>();
                var logSink = new InMemoryLogSink();
                services.AddSingleton<IInMemoryLogSink>(logSink);
                services.AddSingleton<ILoggerProvider>(new UiLoggerProvider(logSink));

                // ViewModels
                services.AddTransient<MainViewModel>();
                services.AddTransient<LoginViewModel>();
                services.AddTransient<DashboardViewModel>();
                services.AddTransient<SettingsViewModel>();
                services.AddTransient<LogsViewModel>();
                services.AddTransient<TrayViewModel>();

                // Views
                services.AddTransient<MainWindow>();
            })
            .Build();
    }

    protected override async void OnStartup(StartupEventArgs e)
    {
        await _host.StartAsync();

        await EnsureHelperIsRunningAsync();

        // Fire and forget update checker
        _ = CheckForUpdatesAsync();

        _notifyIcon = (TaskbarIcon)FindResource("NotifyIcon");
        _notifyIcon.DataContext = _host.Services.GetRequiredService<TrayViewModel>();

        var mainWindow = _host.Services.GetRequiredService<MainWindow>();
        mainWindow.Closing += MainWindow_Closing;
        mainWindow.Show();

        base.OnStartup(e);
    }

    private void MainWindow_Closing(object? sender, CancelEventArgs e)
    {
        if (!_isExiting)
        {
            e.Cancel = true;
            if (sender is Window window)
            {
                window.Hide();
            }
        }
    }

    protected override async void OnExit(ExitEventArgs e)
    {
        _isExiting = true;
        _notifyIcon?.Dispose();

        using (_host)
        {
            await _host.StopAsync();
        }
        base.OnExit(e);
    }

    private async Task EnsureHelperIsRunningAsync()
    {
        var logger = _host.Services.GetService<ILogger<App>>();
        var helperClient = _host.Services.GetService<IHelperClient>();

        // 1. Check if an existing helper is already running and responsive
        if (helperClient != null)
        {
            try
            {
                using var cts = new CancellationTokenSource(1500);
                var pingRes = await helperClient.PingAsync(cts.Token);
                if (pingRes.IsSuccess && pingRes.Value)
                {
                    logger?.LogInformation("Existing Helper process is alive and responding to IPC.");
                    return;
                }
            }
            catch { }
        }

        // 2. Clean up any stale or unresponsive helper processes
        var existingHelpers = System.Diagnostics.Process.GetProcessesByName("OverREALITY.Helper");
        foreach (var proc in existingHelpers)
        {
            try
            {
                logger?.LogWarning("Found existing unresponsive Helper process (PID {Pid}). Terminating.", proc.Id);
                proc.Kill();
                proc.WaitForExit(2000);
            }
            catch (Exception ex)
            {
                logger?.LogWarning(ex, "Failed to terminate unresponsive Helper process {Pid}.", proc.Id);
            }
        }

        // 3. Locate the Helper executable
        var baseDir = Path.GetDirectoryName(Environment.ProcessPath) ?? AppDomain.CurrentDomain.BaseDirectory;
        var candidatePaths = new[]
        {
            Path.Combine(baseDir, "OverREALITY.Helper.exe"),
            Path.Combine(baseDir, "..", "helper", "OverREALITY.Helper.exe"),
            Path.GetFullPath(Path.Combine(baseDir, "..", "..", "..", "..", "publish_build", "helper", "OverREALITY.Helper.exe")),
            @"C:\Program Files\Stealthy VPN\OverREALITY.Helper.exe"
        };

        string? helperPath = candidatePaths.FirstOrDefault(File.Exists);

        if (string.IsNullOrEmpty(helperPath) || !File.Exists(helperPath))
        {
            logger?.LogError("OverREALITY.Helper.exe not found. Searched: {Paths}", string.Join(", ", candidatePaths));
            return;
        }

        // 4. Launch Helper with elevation
        var helperDir = Path.GetDirectoryName(helperPath)!;
        var startInfo = new System.Diagnostics.ProcessStartInfo
        {
            FileName = helperPath,
            WorkingDirectory = helperDir,
            UseShellExecute = true,
            Verb = "runas"
        };

        try
        {
            logger?.LogInformation("Starting elevated helper: {Path} (WorkingDir: {Dir})", helperPath, helperDir);
            var proc = System.Diagnostics.Process.Start(startInfo);
            if (proc == null)
            {
                logger?.LogError("Process.Start returned null for helper.");
                return;
            }
        }
        catch (System.ComponentModel.Win32Exception ex) when (ex.NativeErrorCode == 1223) // ERROR_CANCELLED (user clicked No on UAC)
        {
            logger?.LogWarning("User declined UAC elevation prompt for OverREALITY.Helper.");
            return;
        }
        catch (Exception ex)
        {
            logger?.LogError(ex, "Failed to launch elevated helper process.");
            return;
        }

        // 5. Wait for IPC readiness
        if (helperClient != null)
        {
            var sw = System.Diagnostics.Stopwatch.StartNew();
            const int maxWaitMs = 15000;
            string lastPingError = "No ping attempt made yet";

            while (sw.ElapsedMilliseconds < maxWaitMs)
            {
                try
                {
                    using var pingCts = new CancellationTokenSource(1000);
                    var pingResult = await helperClient.PingAsync(pingCts.Token);
                    if (pingResult.IsSuccess && pingResult.Value)
                    {
                        logger?.LogInformation("Helper process verified responsive via IPC in {Elapsed}ms.", sw.ElapsedMilliseconds);
                        return;
                    }
                    else if (!pingResult.IsSuccess)
                    {
                        lastPingError = $"{pingResult.Error?.Code}: {pingResult.Error?.Message}";
                    }
                }
                catch (Exception ex)
                {
                    lastPingError = ex.Message;
                    logger?.LogDebug(ex, "Ping attempt failed after {Elapsed}ms.", sw.ElapsedMilliseconds);
                }

                await Task.Delay(300);
            }

            logger?.LogWarning("Helper process was started but did not respond to IPC ping within {Timeout}ms. Last error: {LastError}", maxWaitMs, lastPingError);
        }
    }

    private async System.Threading.Tasks.Task CheckForUpdatesAsync()
    {
        try
        {
            using var client = new System.Net.Http.HttpClient();
            client.DefaultRequestHeaders.Add("User-Agent", "OverREALITY-Update-Checker");
            var response = await client.GetAsync("https://api.github.com/repos/adikul1023/RealityTunnel/releases/latest");
            if (response.IsSuccessStatusCode)
            {
                var json = await response.Content.ReadAsStringAsync();
                var match = System.Text.RegularExpressions.Regex.Match(json, @"""tag_name"":\s*""([^""]+)""");
                if (match.Success)
                {
                    var latestTag = match.Groups[1].Value;
                    var currentVersion = "v" + System.Reflection.Assembly.GetExecutingAssembly().GetName().Version?.ToString(3);
                    if (!string.IsNullOrEmpty(latestTag) && latestTag != currentVersion)
                    {
                        var result = MessageBox.Show(
                            $"A new version ({latestTag}) of Stealthy is available! Would you like to update now?",
                            "Update Available",
                            MessageBoxButton.YesNo,
                            MessageBoxImage.Information);
                        
                        if (result == MessageBoxResult.Yes)
                        {
                            var downloadUrl = "https://github.com/adikul1023/StealthyDownloads/releases/latest/download/setup.exe";
                            var psi = new System.Diagnostics.ProcessStartInfo
                            {
                                FileName = downloadUrl,
                                UseShellExecute = true
                            };
                            System.Diagnostics.Process.Start(psi);
                        }
                    }
                }
            }
        }
        catch (System.Exception ex)
        {
            System.Diagnostics.Debug.WriteLine($"Update check failed: {ex.Message}");
        }
    }
}
