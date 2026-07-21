using Microsoft.Extensions.DependencyInjection;
using Microsoft.UI.Xaml;
using RealityTunnel.Services;
using System;
using System.Net.Http;

namespace RealityTunnel;

public partial class App : Application
{
    public new static App Current => (App)Application.Current;
    public IServiceProvider Services { get; }

    public App()
    {
        StartupLogger.Log("[4] Construct App() entered");
        this.InitializeComponent();
        this.UnhandledException += (s, e) =>
        {
            StartupLogger.Log($"[App.UnhandledException] {e.Exception}");
            try { System.IO.File.AppendAllText(@"D:\My projects\VPN\OverREALITY\startup_error.txt", $"{DateTime.Now}: XAML Unhandled: {e.Exception}\nMessage: {e.Message}\n"); } catch { }
            e.Handled = true;
        };
        StartupLogger.Log("[4b] Before ConfigureServices()");
        Services = ConfigureServices();
        StartupLogger.Log("[6] Host.Build() / ConfigureServices completed");
    }

    private static IServiceProvider ConfigureServices()
    {
        var services = new ServiceCollection();

        // Register services
        services.AddSingleton<ClientLogger>();
        services.AddSingleton<SecureStorageService>();
        services.AddSingleton<TokenService>();
        services.AddSingleton<LicenseService>();
        // Setup API Base URL based on environment or configuration
        string apiBaseUrl = Environment.GetEnvironmentVariable("STEALTHY_API_URL") ?? "https://api.stealthy.co.in";
        services.AddTransient<ResilientHttpClientHandler>(sp => new ResilientHttpClientHandler(new HttpClientHandler()));

        services.AddHttpClient<OracleApiClient>(client =>
        {
            client.BaseAddress = new Uri(apiBaseUrl);
            client.Timeout = TimeSpan.FromSeconds(10);
            client.DefaultRequestHeaders.UserAgent.ParseAdd("Stealthy-Windows/1.0.0-beta");
        }).ConfigurePrimaryHttpMessageHandler<ResilientHttpClientHandler>();

        services.AddSingleton<AuthenticationService>();
        services.AddSingleton<ConfigurationProvider>();
        services.AddSingleton<DeviceHeartbeatService>();
        
        // Register legacy controllers that the VpnSessionManager needs
        services.AddSingleton<XrayController>();
        // Register concrete backends for Phase 3A dual-backend rollout
        services.AddSingleton<InProcessVpnBackend>();
        services.AddSingleton<NamedPipeVpnBackend>();
        services.AddSingleton<IVpnBackendResolver, VpnBackendResolver>();
        services.AddSingleton<IVpnBackend>(sp => sp.GetRequiredService<IVpnBackendResolver>().Resolve());
        services.AddSingleton<VpnSessionManager>();

        // Register MainWindow so it can accept injected dependencies if desired
        services.AddTransient<MainWindow>();

        return services.BuildServiceProvider();
    }

    protected override void OnLaunched(LaunchActivatedEventArgs args)
    {
        StartupLogger.Log("[5] OnLaunched() entered");
        StartupLogger.Log("[7] Resolving MainWindow from DI");
        var mainWindow = Services.GetRequiredService<MainWindow>();
        StartupLogger.Log("[7b] After resolving MainWindow from DI");
        m_window = mainWindow;
        StartupLogger.Log("[11] Before Activate()");
        m_window.Activate();
        StartupLogger.Log("[12] After Activate()");

        if (!string.IsNullOrWhiteSpace(args.Arguments) && args.Arguments.Contains("exchange_token="))
        {
            _ = mainWindow.HandleActivationUriAsync(args.Arguments);
        }
    }

    public void BringToForeground(Microsoft.Windows.AppLifecycle.AppActivationArguments args)
    {
        if (m_window is MainWindow window)
        {
            window.DispatcherQueue.TryEnqueue(() =>
            {
                window.ShowFromTray();
                
                // If it's a protocol activation, we handle it
                if (args.Kind == Microsoft.Windows.AppLifecycle.ExtendedActivationKind.Launch)
                {
                    var launchArgs = args.Data as Microsoft.Windows.AppLifecycle.AppActivationArguments; // or cast to appropriate
                    // For now, if we need to parse arguments from redirection, we would do it here
                    // e.g. window.HandleActivationUriAsync(...)
                }
            });
        }
    }

    private Window? m_window;
}
