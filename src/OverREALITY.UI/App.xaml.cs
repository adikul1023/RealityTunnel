using System;
using System.ComponentModel;
using System.Windows;
using Hardcodet.Wpf.TaskbarNotification;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using OverREALITY.Configuration;
using OverREALITY.Core;
using OverREALITY.Infrastructure;
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
        EnsureHelperIsRunning();

        await _host.StartAsync();

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

    private void EnsureHelperIsRunning()
    {
        var helperProcesses = System.Diagnostics.Process.GetProcessesByName("OverREALITY.Helper");
        if (helperProcesses.Length > 0)
        {
            return;
        }

        try
        {
            var baseDir = System.IO.Path.GetDirectoryName(Environment.ProcessPath) ?? System.AppDomain.CurrentDomain.BaseDirectory;
            var helperPath = System.IO.Path.Combine(baseDir, "OverREALITY.Helper.exe");
            if (!System.IO.File.Exists(helperPath))
            {
                System.Diagnostics.Debug.WriteLine($"Helper not found at: {helperPath}");
                return;
            }

            var startInfo = new System.Diagnostics.ProcessStartInfo
            {
                FileName = helperPath,
                UseShellExecute = true,
                Verb = "runas",
                WindowStyle = System.Diagnostics.ProcessWindowStyle.Hidden,
                CreateNoWindow = true
            };
            System.Diagnostics.Process.Start(startInfo);
        }
        catch (System.Exception ex)
        {
            System.Diagnostics.Debug.WriteLine($"Failed to start helper: {ex.Message}");
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
                    var latestTag = match.Groups[1].Value; // e.g. "v1.1.4"
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
