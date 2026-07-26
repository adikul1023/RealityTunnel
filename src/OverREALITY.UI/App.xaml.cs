using System.ComponentModel;
using System.Windows;
using Hardcodet.Wpf.TaskbarNotification;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using OverREALITY.Configuration;
using OverREALITY.Core;
using OverREALITY.Infrastructure;
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
        if (helperProcesses.Length == 0)
        {
            try
            {
                var baseDir = System.IO.Path.GetDirectoryName(Environment.ProcessPath) ?? System.AppDomain.CurrentDomain.BaseDirectory;
                var helperPath = System.IO.Path.Combine(baseDir, "OverREALITY.Helper.exe");
                if (System.IO.File.Exists(helperPath))
                {
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
            }
            catch (System.Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"Failed to start helper: {ex.Message}");
            }
        }
    }
}
