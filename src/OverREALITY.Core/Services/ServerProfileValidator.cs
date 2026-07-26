using OverREALITY.Shared.Api.Configuration;
using OverREALITY.Shared.Errors;
using OverREALITY.Shared.Interfaces;

namespace OverREALITY.Core.Services;

public class ServerProfileValidator : IServerProfileValidator
{
    public Result<bool, ProvisioningError> Validate(ServerProfileDto profile)
    {
        if (profile == null)
        {
            return Result<bool, ProvisioningError>.Failure(new ProvisioningError { Code = "PROFILE_NULL", Message = "Profile cannot be null." });
        }

        if (string.IsNullOrWhiteSpace(profile.Server))
            return Result<bool, ProvisioningError>.Failure(new ProvisioningError { Code = "INVALID_SERVER", Message = "Server address is missing." });

        if (profile.Port <= 0 || profile.Port > 65535)
            return Result<bool, ProvisioningError>.Failure(new ProvisioningError { Code = "INVALID_PORT", Message = "Port is invalid." });

        if (string.IsNullOrWhiteSpace(profile.Uuid))
            return Result<bool, ProvisioningError>.Failure(new ProvisioningError { Code = "INVALID_UUID", Message = "UUID is missing." });

        if (string.IsNullOrWhiteSpace(profile.Transport))
            return Result<bool, ProvisioningError>.Failure(new ProvisioningError { Code = "INVALID_TRANSPORT", Message = "Transport is missing." });

        return Result<bool, ProvisioningError>.Success(true);
    }
}
