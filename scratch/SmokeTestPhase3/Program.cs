using System;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using OverREALITY.Core;
using OverREALITY.Configuration;
using OverREALITY.Infrastructure;
using OverREALITY.Shared.Interfaces;
using OverREALITY.Shared.Api;
using OverREALITY.Shared.Api.Configuration;
using OverREALITY.Shared.Api.VpnRuntime;

namespace SmokeTestPhase3
{
    class Program
    {
        static async Task Main(string[] args)
        {
            var host = Host.CreateDefaultBuilder(args)
                .ConfigureLogging(logging => {
                    logging.ClearProviders();
                    logging.AddConsole();
                    logging.SetMinimumLevel(LogLevel.Debug);
                })
                .ConfigureServices(services => {
                    services.AddCoreServices();
                    services.AddConfigurationServices();
                    services.AddInfrastructureServices();
                })
                .Build();

            var configBuilder = host.Services.GetRequiredService<IConfigurationBuilder>();
            var helperClient = host.Services.GetRequiredService<IHelperClient>();

            var mockProfile = new ServerProfileDto
            {
                Server = "edge.stealthy.co.in",
                Port = 443,
                Uuid = "c9398f56-6f7d-41a4-9669-0f622645600d",
                PublicKey = "n3Z0F39zJ-s8H_oR-6gPq-1J7Q0nQ-1wW1_1T0mQ-1o",
                ShortId = "1a2b3c4d5e6f7a8b",
                Sni = "edge.stealthy.co.in",
                Transport = "vless",
                Fingerprint = "chrome"
            };

            Console.WriteLine("Building configuration...");
            var config = configBuilder.Build(mockProfile);

            Console.WriteLine("Sending configuration to Helper...");
            var startReq = new StartVpnRequest { Config = config };
            
            var result = await helperClient.StartAsync(startReq, CancellationToken.None);
            
            if (result.IsSuccess) {
                Console.WriteLine("Helper started successfully.");
            } else {
                Console.WriteLine("Helper failed: " + result.Error?.Message + " (Code: " + result.Error?.Code + ")");
            }
        }
    }
}
