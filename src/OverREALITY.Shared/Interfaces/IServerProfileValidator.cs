using OverREALITY.Shared.Api.Configuration;
using OverREALITY.Shared.Errors;

namespace OverREALITY.Shared.Interfaces;

public interface IServerProfileValidator
{
    Result<bool, ProvisioningError> Validate(ServerProfileDto profile);
}
