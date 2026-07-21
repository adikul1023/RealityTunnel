using Microsoft.UI.Dispatching;
using Microsoft.Windows.AppLifecycle;
using System;
using System.Threading;
using System.Threading.Tasks;

namespace RealityTunnel;

public static class Program
{
    [STAThread]
    static void Main(string[] args)
    {
        try
        {
            StartupLogger.Log("[1] Enter Main()");
            AppDomain.CurrentDomain.UnhandledException += (s, e) =>
            {
                StartupLogger.Log($"[UnhandledException] {e.ExceptionObject}");
                try { System.IO.File.AppendAllText(@"D:\My projects\VPN\OverREALITY\startup_error.txt", $"{DateTime.Now}: AppDomain Unhandled: {e.ExceptionObject}\n"); } catch { }
            };

            WinRT.ComWrappersSupport.InitializeComWrappers();
            StartupLogger.Log("[2] DecideRedirection() entered");
            bool isRedirect = DecideRedirection().GetAwaiter().GetResult();
            StartupLogger.Log($"[3] DecideRedirection() completed (isRedirect={isRedirect})");
            if (isRedirect)
            {
                StartupLogger.Log("[Redirection] Exiting because instance already active");
                try { System.IO.File.AppendAllText(@"D:\My projects\VPN\OverREALITY\startup_error.txt", $"{DateTime.Now}: Main early exit because DecideRedirection returned true (instance already active).\n"); } catch { }
            }
            if (!isRedirect)
            {
                StartupLogger.Log("[3b] Before Application.Start()");
                Microsoft.UI.Xaml.Application.Start((p) =>
                {
                    StartupLogger.Log("[3c] Inside Application.Start() callback");
                    var context = new DispatcherQueueSynchronizationContext(
                        DispatcherQueue.GetForCurrentThread());
                    SynchronizationContext.SetSynchronizationContext(context);
                    StartupLogger.Log("[3d] Before constructing App()");
                    new App();
                });
            }
        }
        catch (Exception ex)
        {
            StartupLogger.Log($"[Fatal Main Exception] {ex}");
            try { System.IO.File.AppendAllText(@"D:\My projects\VPN\OverREALITY\startup_error.txt", $"{DateTime.Now}: Fatal Main Exception: {ex}\n"); } catch { }
            throw;
        }
    }
    private static async Task<bool> DecideRedirection()
    {
        bool isRedirect = false;
        AppActivationArguments args = AppInstance.GetCurrent().GetActivatedEventArgs();
        AppInstance keyInstance = AppInstance.FindOrRegisterForKey("RealityTunnelSingleInstance");

        if (keyInstance.IsCurrent)
        {
            keyInstance.Activated += OnActivated;
        }
        else
        {
            isRedirect = true;
            await keyInstance.RedirectActivationToAsync(args);
        }
        return isRedirect;
    }

    private static void OnActivated(object? sender, AppActivationArguments args)
    {
        var app = Microsoft.UI.Xaml.Application.Current as App;
        app?.BringToForeground(args);
    }
}
