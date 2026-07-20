using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;

namespace RealityTunnel.Helper;

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
                options.ServiceName = "RealityTunnelHelper";
            })
            .ConfigureServices((hostContext, services) =>
            {
                services.AddSingleton<HelperLogger>();
                services.AddSingleton<PipeSecurityHelper>();
                services.AddHostedService<PipeServerWorker>();
            });
}
