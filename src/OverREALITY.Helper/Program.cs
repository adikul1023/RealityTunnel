using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;

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
            .ConfigureServices((hostContext, services) =>
            {
                services.AddSingleton<HelperStateMachine>();
                services.AddSingleton<IpcServer>();
                services.AddSingleton<SingboxProcessManager>();
                services.AddSingleton<ProcessSupervisor>();
                services.AddHostedService<HelperWorker>();
            });
}
