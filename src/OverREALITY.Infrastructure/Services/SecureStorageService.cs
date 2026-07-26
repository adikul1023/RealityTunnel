using System;
using System.Security.Cryptography;
using System.Text;
using System.Threading.Tasks;
using OverREALITY.Shared.Interfaces;
using Microsoft.Extensions.Logging;
using System.IO;

namespace OverREALITY.Infrastructure.Services;

public class SecureStorageService : ISecureStorage
{
    private readonly ILogger<SecureStorageService> _logger;
    private readonly string _storageDir;

    public SecureStorageService(ILogger<SecureStorageService> logger)
    {
        _logger = logger;
        var appData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        _storageDir = Path.Combine(appData, "OverREALITY", "Secure");
        Directory.CreateDirectory(_storageDir);
    }

    public Task SaveSecureAsync(string key, string value)
    {
        try
        {
            var dataToProtect = Encoding.UTF8.GetBytes(value);
            var protectedData = ProtectedData.Protect(dataToProtect, null, DataProtectionScope.CurrentUser);
            var filePath = Path.Combine(_storageDir, $"{key}.dat");
            File.WriteAllBytes(filePath, protectedData);
            return Task.CompletedTask;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to save secure data for key: {Key}", key);
            throw new CryptographicException($"Failed to secure data for key {key}", ex);
        }
    }

    public Task<string?> GetSecureAsync(string key)
    {
        try
        {
            var filePath = Path.Combine(_storageDir, $"{key}.dat");
            if (File.Exists(filePath))
            {
                var protectedData = File.ReadAllBytes(filePath);
                var unprotectedData = ProtectedData.Unprotect(protectedData, null, DataProtectionScope.CurrentUser);
                return Task.FromResult<string?>(Encoding.UTF8.GetString(unprotectedData));
            }
            return Task.FromResult<string?>(null);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to retrieve secure data for key: {Key}", key);
            throw new CryptographicException($"Failed to retrieve secured data for key {key}", ex);
        }
    }

    public Task DeleteSecureAsync(string key)
    {
        try
        {
            var filePath = Path.Combine(_storageDir, $"{key}.dat");
            if (File.Exists(filePath))
            {
                File.Delete(filePath);
            }
            return Task.CompletedTask;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to delete secure data for key: {Key}", key);
            throw new IOException($"Failed to delete secured data for key {key}", ex);
        }
    }
}
