using System;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using OverREALITY.Shared.Api.Configuration;
using OverREALITY.Shared.Errors;
using OverREALITY.Shared.Interfaces;

namespace OverREALITY.Core.Services;

public class ConnectionProvisioningService : IConnectionProvisioningService
{
    private readonly IApiClient _apiClient;
    private readonly IConfigurationBuilder _configurationBuilder;
    private readonly IServerProfileValidator _validator;
    private readonly ILogger<ConnectionProvisioningService> _logger;

    public ConnectionProvisioningService(IApiClient apiClient, IConfigurationBuilder configurationBuilder, IServerProfileValidator validator, ILogger<ConnectionProvisioningService> logger)
    {
        _apiClient = apiClient;
        _configurationBuilder = configurationBuilder;
        _validator = validator;
        _logger = logger;
    }

    public async Task<Result<VPNConfig, ProvisioningError>> ConnectProvisionAsync(CancellationToken cancellationToken = default)
    {
        var profileResult = await _apiClient.GetAsync<ClientConfigResponse>("/api/client/config", cancellationToken);
        
        if (!profileResult.IsSuccess || profileResult.Value == null)
        {
            _logger.LogError("Failed to fetch server profile.");
            return Result<VPNConfig, ProvisioningError>.Failure(new ProvisioningError 
            { 
                Message = profileResult.Error?.Message ?? "Failed to fetch server profile", 
                Code = "PROFILE_FETCH_FAILED" 
            });
        }

        var profile = profileResult.Value.VpnProfile;
        var validationResult = _validator.Validate(profile);
        if (!validationResult.IsSuccess)
        {
            _logger.LogError("Invalid server profile received.");
            return Result<VPNConfig, ProvisioningError>.Failure(validationResult.Error!);
        }

        try
        {
            var config = _configurationBuilder.Build(profile);
            return Result<VPNConfig, ProvisioningError>.Success(config);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to build VPN configuration");
            return Result<VPNConfig, ProvisioningError>.Failure(new ProvisioningError 
            { 
                Message = "An error occurred while building the VPN configuration.", 
                Code = "BUILD_ERROR", 
                Exception = ex 
            });
        }
    }
}
