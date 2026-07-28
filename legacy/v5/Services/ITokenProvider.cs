using System.Threading.Tasks;

namespace RealityTunnel.Services;

public interface ITokenProvider
{
    Task<string?> GetValidAccessTokenAsync();
}
