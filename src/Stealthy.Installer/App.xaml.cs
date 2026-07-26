using System;
using System.Windows;
using System.Windows.Threading;

namespace Stealthy.Installer
{
    public partial class App : Application
    {
        protected override void OnStartup(StartupEventArgs e)
        {
            base.OnStartup(e);

            // Catch all unhandled exceptions and show a message instead of dying silently
            AppDomain.CurrentDomain.UnhandledException += (s, args) =>
            {
                var ex = args.ExceptionObject as Exception;
                MessageBox.Show($"Fatal error:\n\n{ex?.Message}\n\n{ex?.StackTrace}",
                    "Stealthy Installer Error", MessageBoxButton.OK, MessageBoxImage.Error);
            };

            DispatcherUnhandledException += (s, args) =>
            {
                MessageBox.Show($"UI error:\n\n{args.Exception.Message}\n\n{args.Exception.StackTrace}",
                    "Stealthy Installer Error", MessageBoxButton.OK, MessageBoxImage.Error);
                args.Handled = true;
            };
        }
    }
}
