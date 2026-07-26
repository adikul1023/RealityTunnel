using OverREALITY.Shared.Api.Configuration;

namespace OverREALITY.Shared.Interfaces;

public interface IConfigurationBuilder
{
    VPNConfig Build(ServerProfileDto profile);
}
