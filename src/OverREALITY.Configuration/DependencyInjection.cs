using Microsoft.Extensions.DependencyInjection;
using OverREALITY.Shared.Interfaces;

namespace OverREALITY.Configuration;

public static class DependencyInjection
{
    public static IServiceCollection AddConfigurationServices(this IServiceCollection services)
    {
        services.AddSingleton<ISingboxTemplateProvider, SingboxTemplateProvider>();
        services.AddSingleton<IConfigurationBuilder, ConfigurationBuilder>();
        return services;
    }
}
