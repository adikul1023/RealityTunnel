using Microsoft.Extensions.DependencyInjection;
using OverREALITY.Shared.Interfaces;
using OverREALITY.Infrastructure.Services;

namespace OverREALITY.Infrastructure;

public static class DependencyInjection
{
    public static IServiceCollection AddInfrastructureServices(this IServiceCollection services)
    {
        services.AddLogging();
        services.AddHttpClient();

        services.AddSingleton<ISettingsService, SettingsService>();
        services.AddSingleton<IDomainResolver, DomainResolver>();
        services.AddSingleton<IFeatureManager, FeatureManager>();
        services.AddSingleton<ISecureStorage, SecureStorageService>();
        services.AddSingleton<ISessionManager, SessionManager>();

        services.AddSingleton<IHelperClient, HelperClient>();

        services.AddSingleton<IOperationContext, OperationContext>();

        return services;
    }
}
