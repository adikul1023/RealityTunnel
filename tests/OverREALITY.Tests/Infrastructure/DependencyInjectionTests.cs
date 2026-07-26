using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using OverREALITY.Infrastructure;
using OverREALITY.Shared.Interfaces;
using Xunit;

namespace OverREALITY.Tests.Infrastructure;

public class DependencyInjectionTests
{
    [Fact]
    public void AddInfrastructureServices_RegistersAllRequiredServices()
    {
        System.IO.File.WriteAllText("environment.json", "{ \"ApiBaseUrl\": \"https://api.test.com\" }");
        var services = new ServiceCollection();
        services.AddInfrastructureServices();
        var provider = services.BuildServiceProvider();

        Assert.NotNull(provider.GetService<ILoggerFactory>());
        Assert.NotNull(provider.GetService<ISettingsService>());
        Assert.NotNull(provider.GetService<IDomainResolver>());
        Assert.NotNull(provider.GetService<IFeatureManager>());
        Assert.NotNull(provider.GetService<ISecureStorage>());
        Assert.NotNull(provider.GetService<ISessionManager>());
    }
}
