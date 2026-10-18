using System;
using System.IO;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using OverREALITY.Shared.Logging;

namespace OverREALITY.Helper;

public class Program
{
    public static void Main(string[] args)
    {
        CreateHostBuilder(args).Build().Run();
    }

    public static IHostBuilder CreateHostBuilder(string[] args) =>
        Host.CreateDefaultBuilder(args)
            .UseWindowsService(options =>
            {
                options.ServiceName = "OverREALITY VPN Helper";
            })
            .ConfigureLogging((hostContext, logging) =>
            {
                logging.ClearProviders();
                logging.AddConsole();
                try
                {
                    var logDir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData), "OverREALITY");
                    if (!Directory.Exists(logDir))
                    {
                        Directory.CreateDirectory(logDir);
                    }
                    var logFile = Path.Combine(logDir, "helper.log");
                    logging.AddProvider(new FileLoggerProvider(logFile));
                }
                catch { }
            })
            .ConfigureServices((hostContext, services) =>
            {
                services.AddSingleton<HelperStateMachine>();
                services.AddSingleton<IpcServer>();
                services.AddSingleton<SingboxProcessManager>();
                services.AddSingleton<ProcessSupervisor>();
                services.AddHostedService<HelperWorker>();
            });
}
