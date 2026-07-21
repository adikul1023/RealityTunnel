using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;

namespace RealityTunnel.Helper;

public class Program
{
    public static void Main(string[] args)
    {
        AppDomain.CurrentDomain.UnhandledException += (s, e) =>
        {
            LogFatalError("UnhandledException", e.ExceptionObject as Exception);
        };

        try
        {
            CreateHostBuilder(args).Build().Run();
        }
        catch (Exception ex)
        {
            LogFatalError("MainStartupException", ex);
            throw;
        }
    }

    private static void LogFatalError(string source, Exception? ex)
    {
        try
        {
            string logDir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData), "RealityTunnel");
            if (!Directory.Exists(logDir)) Directory.CreateDirectory(logDir);
            string logPath = Path.Combine(logDir, "helper_crash.log");
            string message = $"[{DateTime.UtcNow:O}] [{source}] Fatal error:\n{ex}\n\n";
            File.AppendAllText(logPath, message);
        }
        catch { }
    }

    public static IHostBuilder CreateHostBuilder(string[] args) =>
        Host.CreateDefaultBuilder(args)
            .UseWindowsService(options =>
            {
                options.ServiceName = "RealityTunnelHelper";
            })
            .ConfigureServices((hostContext, services) =>
            {
                services.AddSingleton<HelperLogger>();
                services.AddSingleton<PipeSecurityHelper>();
                services.AddHostedService<PipeServerWorker>();
            });
}
