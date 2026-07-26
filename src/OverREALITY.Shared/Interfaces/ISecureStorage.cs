using System.Threading.Tasks;

namespace OverREALITY.Shared.Interfaces;

public interface ISecureStorage
{
    Task SaveSecureAsync(string key, string value);
    Task<string?> GetSecureAsync(string key);
    Task DeleteSecureAsync(string key);
}
