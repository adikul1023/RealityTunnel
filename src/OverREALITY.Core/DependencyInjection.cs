using Microsoft.Extensions.DependencyInjection;
using OverREALITY.Core.Services;
using OverREALITY.Shared.Interfaces;

namespace OverREALITY.Core;

public static class DependencyInjection
{
    public static IServiceCollection AddCoreServices(this IServiceCollection services)
    {
        services.AddHttpClient<IAuthenticationApi, AuthenticationApi>();
        services.AddHttpClient<IApiClient, ApiClient>();
        
        services.AddSingleton<ITokenProvider, TokenProvider>();
        services.AddSingleton<ISessionFactory, SessionFactory>();
        services.AddSingleton<IAuthService, AuthenticationService>();
        services.AddSingleton<IConnectionProvisioningService, ConnectionProvisioningService>();

        services.AddSingleton<IConnectionStateManager, ConnectionStateManager>();
        services.AddSingleton<IConnectionService, ConnectionService>();
        services.AddSingleton<IEventBus, InMemoryEventBus>();

        services.AddSingleton<IServerProfileValidator, ServerProfileValidator>();

        return services;
    }
}
