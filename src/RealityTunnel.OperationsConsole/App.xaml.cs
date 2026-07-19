using System;
using System.Windows;
using Microsoft.Extensions.DependencyInjection;
using RealityTunnel.OperationsConsole.Services;
using RealityTunnel.OperationsConsole.ViewModels;
using RealityTunnel.OperationsConsole.Views;

namespace RealityTunnel.OperationsConsole
{
    public partial class App : Application
    {
        private static IServiceProvider? _serviceProvider;
        public static IServiceProvider Services => _serviceProvider ?? throw new InvalidOperationException("Service provider not initialized");

        private Window? _currentActiveWindow;

        protected override void OnStartup(StartupEventArgs e)
        {
            base.OnStartup(e);

            this.DispatcherUnhandledException += (s, args) => {
                var ex = args.Exception;
                string log = "Dispatcher Exception:\n" + ex.ToString() + "\n";
                while (ex.InnerException != null) {
                    ex = ex.InnerException;
                    log += "\n--- Inner ---\n" + ex.ToString() + "\n";
                }
                System.IO.File.WriteAllText(@"D:\My projects\VPN\OverREALITY\crash.log", log);
                args.Handled = true; // prevent immediate exit
                Environment.Exit(1);
            };

            AppDomain.CurrentDomain.UnhandledException += (s, args) => {
                var ex = args.ExceptionObject as Exception;
                string log = "AppDomain Exception:\n" + ex?.ToString() + "\n";
                while (ex?.InnerException != null) {
                    ex = ex.InnerException;
                    log += "\n--- Inner ---\n" + ex.ToString() + "\n";
                }
                System.IO.File.WriteAllText(@"D:\My projects\VPN\OverREALITY\crash2.log", log);
            };

            var services = new ServiceCollection();
            ConfigureServices(services);
            _serviceProvider = services.BuildServiceProvider();

            var navService = _serviceProvider.GetRequiredService<INavigationService>();
            navService.OnNavigateToLogin += HandleNavigateToLogin;
            navService.OnNavigateToMain += HandleNavigateToMain;

            // Start at LoginWindow
            HandleNavigateToLogin();
        }

        private static void ConfigureServices(IServiceCollection services)
        {
            // Services
            services.AddSingleton<ISessionService, SessionService>();
            services.AddSingleton<INavigationService, NavigationService>();
            services.AddSingleton<IDialogService, DialogService>();
            services.AddHttpClient("AdminApiClient");
            services.AddSingleton<IAdminApiService, AdminApiService>();

            // ViewModels
            services.AddTransient<LoginViewModel>();
            services.AddTransient<MainViewModel>();
            services.AddTransient<DashboardViewModel>();
            services.AddTransient<UsersViewModel>();
            services.AddTransient<UserDetailsViewModel>();
            services.AddTransient<SubscriptionsViewModel>();
            services.AddTransient<PaymentsViewModel>();
            services.AddTransient<InfrastructureViewModel>();
            services.AddTransient<LogsViewModel>();
            services.AddTransient<SettingsViewModel>();

            // Views / Windows
            services.AddTransient<LoginWindow>();
            services.AddTransient<MainWindow>();
            services.AddTransient<DashboardView>();
            services.AddTransient<UsersView>();
            services.AddTransient<UserDetailsPanel>();
            services.AddTransient<SubscriptionsView>();
            services.AddTransient<PaymentsView>();
            services.AddTransient<InfrastructureView>();
            services.AddTransient<LogsView>();
            services.AddTransient<SettingsView>();
        }

        private void HandleNavigateToLogin()
        {
            Dispatcher.Invoke(() =>
            {
                var loginWin = _serviceProvider!.GetRequiredService<LoginWindow>();
                var oldWin = _currentActiveWindow;
                _currentActiveWindow = loginWin;
                loginWin.Show();

                if (oldWin != null && oldWin != loginWin)
                {
                    oldWin.Close();
                }
            });
        }

        private void HandleNavigateToMain()
        {
            Dispatcher.Invoke(() =>
            {
                var mainWin = _serviceProvider!.GetRequiredService<MainWindow>();
                var oldWin = _currentActiveWindow;
                _currentActiveWindow = mainWin;
                mainWin.Show();

                if (oldWin != null && oldWin != mainWin)
                {
                    oldWin.Close();
                }
            });
        }

        protected override void OnExit(ExitEventArgs e)
        {
            if (_serviceProvider != null)
            {
                var sessionService = _serviceProvider.GetService<ISessionService>();
                sessionService?.ClearSession();
            }
            base.OnExit(e);
        }
    }
}
