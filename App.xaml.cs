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
        this.InitializeComponent();
        Services = ConfigureServices();
    }

    private static IServiceProvider ConfigureServices()
    {
        var services = new ServiceCollection();

        // Register services
        services.AddSingleton<ClientLogger>();
        services.AddSingleton<SecureStorageService>();
        services.AddSingleton<TokenService>();
        services.AddSingleton<LicenseService>();
        // Setup API Base URL based on environment
#if DEBUG
        string apiBaseUrl = "https://staging-api.stealthy.co.in";
#else
        string apiBaseUrl = "https://api.stealthy.co.in";
#endif

        services.AddTransient<ResilientHttpClientHandler>(sp => new ResilientHttpClientHandler(new HttpClientHandler()));

        services.AddHttpClient<OracleApiClient>(client =>
        {
            client.BaseAddress = new Uri(apiBaseUrl);
            client.Timeout = TimeSpan.FromSeconds(10);
            client.DefaultRequestHeaders.UserAgent.ParseAdd("Stealthy-Windows/1.0.0-beta");
        }).ConfigurePrimaryHttpMessageHandler<ResilientHttpClientHandler>();

        services.AddSingleton<AuthenticationService>();
        services.AddSingleton<ConfigurationProvider>();
        
        // Register legacy controllers that the VpnSessionManager needs
        services.AddSingleton<XrayController>();
        services.AddSingleton<VpnSessionManager>();

        // Register MainWindow so it can accept injected dependencies if desired
        services.AddTransient<MainWindow>();

        return services.BuildServiceProvider();
    }

    protected override void OnLaunched(LaunchActivatedEventArgs args)
    {
        var mainWindow = Services.GetRequiredService<MainWindow>();
        m_window = mainWindow;
        m_window.Activate();

        if (!string.IsNullOrWhiteSpace(args.Arguments) && args.Arguments.Contains("exchange_token="))
        {
            _ = mainWindow.HandleActivationUriAsync(args.Arguments);
        }
    }

    private Window? m_window;
}
