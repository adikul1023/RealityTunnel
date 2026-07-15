using System;
using System.Windows;
using Microsoft.Extensions.DependencyInjection;
using Wpf.Ui.Controls;
using RealityTunnel.OperationsConsole.Services;
using RealityTunnel.OperationsConsole.ViewModels;
using RealityTunnel.OperationsConsole.Models;

namespace RealityTunnel.OperationsConsole.Views
{
    public partial class MainWindow : FluentWindow
    {
        private readonly MainViewModel _viewModel;
        private readonly INavigationService _navigationService;
        private readonly IServiceProvider _serviceProvider;

        public MainWindow(MainViewModel viewModel, INavigationService navigationService, IServiceProvider serviceProvider)
        {
            InitializeComponent();
            _viewModel = viewModel;
            _navigationService = navigationService;
            _serviceProvider = serviceProvider;
            DataContext = _viewModel;

            _navigationService.OnNavigate += OnNavigateRequested;
            Loaded += MainWindow_Loaded;
        }

        private void MainWindow_Loaded(object sender, RoutedEventArgs e)
        {
            _viewModel.Initialize();
        }

        private async void OnNavigateRequested(string viewKey, object? parameter)
        {
            await Dispatcher.InvokeAsync(async () =>
            {
                object? viewInstance = viewKey switch
                {
                    "Dashboard" => _serviceProvider.GetRequiredService<DashboardView>(),
                    "Users" => _serviceProvider.GetRequiredService<UsersView>(),
                    "UserDetails" => _serviceProvider.GetRequiredService<UserDetailsPanel>(),
                    "Subscriptions" => _serviceProvider.GetRequiredService<SubscriptionsView>(),
                    "Payments" => _serviceProvider.GetRequiredService<PaymentsView>(),
                    "Infrastructure" => _serviceProvider.GetRequiredService<InfrastructureView>(),
                    "Logs" => _serviceProvider.GetRequiredService<LogsView>(),
                    "Settings" => _serviceProvider.GetRequiredService<SettingsView>(),
                    _ => null
                };

                if (viewInstance != null)
                {
                    // Trigger initialization on child views
                    if (viewInstance is DashboardView dv && dv.DataContext is DashboardViewModel dvm)
                    {
                        await dvm.LoadDashboardAsync();
                    }
                    else if (viewInstance is UsersView uv && uv.DataContext is UsersViewModel uvm)
                    {
                        await uvm.LoadAccountsAsync();
                    }
                    else if (viewInstance is UserDetailsPanel udp && udp.DataContext is UserDetailsViewModel udvm && parameter is UserAccountDisplayModel acc)
                    {
                        await udvm.LoadDetailsAsync(acc);
                    }
                    else if (viewInstance is SubscriptionsView sv && sv.DataContext is SubscriptionsViewModel svm)
                    {
                        await svm.LoadSubscriptionsAsync();
                    }
                    else if (viewInstance is PaymentsView pv && pv.DataContext is PaymentsViewModel pvm)
                    {
                        await pvm.LoadPaymentsAsync();
                    }
                    else if (viewInstance is InfrastructureView iv && iv.DataContext is InfrastructureViewModel ivm)
                    {
                        await ivm.LoadHealthAndStatusAsync();
                    }

                    _viewModel.CurrentViewContent = viewInstance;
                }
            });
        }

        protected override void OnClosed(EventArgs e)
        {
            _navigationService.OnNavigate -= OnNavigateRequested;
            _viewModel.Dispose();
            base.OnClosed(e);
        }
    }
}
