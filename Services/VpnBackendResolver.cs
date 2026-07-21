using System;
using Microsoft.Extensions.DependencyInjection;
using RealityTunnel.Models;

namespace RealityTunnel.Services;

public interface IVpnBackendResolver
{
    IVpnBackend Resolve();
}

public class VpnBackendResolver : IVpnBackendResolver
{
    private readonly IServiceProvider _serviceProvider;
    private readonly ClientLogger _logger;

    public VpnBackendResolver(IServiceProvider serviceProvider, ClientLogger logger)
    {
        _serviceProvider = serviceProvider;
        _logger = logger;
    }

    public IVpnBackend Resolve()
    {
        var envBackendStr = Environment.GetEnvironmentVariable("REALITYTUNNEL_VPN_BACKEND");
        if (!string.IsNullOrWhiteSpace(envBackendStr) &&
            Enum.TryParse<VpnBackendKind>(envBackendStr, true, out var envKind))
        {
            return ResolveKind(envKind, "Environment Variable");
        }

        var configuredKind = AppSettings.Load().VpnBackend;
        return ResolveKind(configuredKind, "AppSettings");
    }

    private IVpnBackend ResolveKind(VpnBackendKind kind, string source)
    {
        switch (kind)
        {
            case VpnBackendKind.NamedPipe:
                _logger.Log(LogLevel.INFO, "BackendResolver", $"VpnBackend: Selected NamedPipeVpnBackend (service-backed IPC mode) from {source}.");
                return _serviceProvider.GetRequiredService<NamedPipeVpnBackend>();

            case VpnBackendKind.InProcess:
            default:
                _logger.Log(LogLevel.INFO, "BackendResolver", $"VpnBackend: Selected InProcessVpnBackend (default dual-backend mode) from {source}.");
                return _serviceProvider.GetRequiredService<InProcessVpnBackend>();
        }
    }
}
