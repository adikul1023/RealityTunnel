using System;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using RealityTunnel.Models;

namespace RealityTunnel.Services;

public class SecureStorageService
{
    private readonly string _storageDir;
    private readonly ClientLogger _logger;

    public SecureStorageService(ClientLogger logger)
    {
        _logger = logger;
        _storageDir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "OverREALITY", "Secure");
        _logger.Log(LogLevel.INFO, "DEVICE_DEBUG", $"Storage path: {_storageDir}");
        if (!Directory.Exists(_storageDir))
        {
            Directory.CreateDirectory(_storageDir);
        }
    }

    public void SaveAccountId(string accountId)
    {
        SaveObject("account_id.dat", accountId);
    }

    public string? GetAccountId()
    {
        return GetObject<string>("account_id.dat");
    }

    public void SaveJwtTokens(JwtTokens tokens)
    {
        SaveObject("tokens.dat", tokens);
    }

    public JwtTokens? GetJwtTokens()
    {
        return GetObject<JwtTokens>("tokens.dat");
    }

    public void SaveLicenseBlob(LicenseBlob blob)
    {
        SaveObject("license.dat", blob);
    }

    public LicenseBlob? GetLicenseBlob()
    {
        return GetObject<LicenseBlob>("license.dat");
    }

    public void SaveVpnProfile(VpnProfile profile)
    {
        SaveObject("vpn_profile.dat", profile);
    }

    public VpnProfile? GetVpnProfile()
    {
        return GetObject<VpnProfile>("vpn_profile.dat");
    }

    public void SaveLastTrustedTimestamp(DateTimeOffset timestamp)
    {
        SaveObject("trusted_time.dat", timestamp);
    }

    public DateTimeOffset? GetLastTrustedTimestamp()
    {
        return GetObject<DateTimeOffset>("trusted_time.dat");
    }

    private void SaveObject<T>(string filename, T obj)
    {
        string json = System.Text.Json.JsonSerializer.Serialize(obj);
        byte[] bytes = Encoding.UTF8.GetBytes(json);
        byte[] protectedBytes = ProtectedData.Protect(bytes, null, DataProtectionScope.CurrentUser);
        File.WriteAllBytes(Path.Combine(_storageDir, filename), protectedBytes);
    }

    private T? GetObject<T>(string filename)
    {
        string path = Path.Combine(_storageDir, filename);
        if (!File.Exists(path)) return default;

        try
        {
            byte[] protectedBytes = File.ReadAllBytes(path);
            byte[] decryptedBytes = ProtectedData.Unprotect(protectedBytes, null, DataProtectionScope.CurrentUser);
            string json = Encoding.UTF8.GetString(decryptedBytes);
            return System.Text.Json.JsonSerializer.Deserialize<T>(json);
        }
        catch
        {
            try
            {
                string corruptPath = path + ".corrupt";
                if (File.Exists(corruptPath)) File.Delete(corruptPath);
                File.Move(path, corruptPath);
            }
            catch { }
            return default;
        }
    }

    public string GetDeviceGuid()
    {
        string path = Path.Combine(_storageDir, "device_guid.dat");
        bool fileExisted = File.Exists(path);
        _logger.Log(LogLevel.INFO, "DEVICE_DEBUG", $"device_guid.dat exists: {fileExisted} (path: {path})");

        if (fileExisted)
        {
            try
            {
                byte[] protectedBytes = File.ReadAllBytes(path);
                byte[] decryptedBytes = ProtectedData.Unprotect(protectedBytes, null, DataProtectionScope.CurrentUser);
                string loadedGuid = Encoding.UTF8.GetString(decryptedBytes);
                _logger.Log(LogLevel.INFO, "DEVICE_DEBUG", $"Loaded GUID from disk: {loadedGuid}");
                return loadedGuid;
            }
            catch (Exception ex)
            {
                // DPAPI decryption failed — file may have been written by a different user or
                // Windows account. Rename so the next call can write a clean one.
                _logger.Log(LogLevel.WARN, "DEVICE_DEBUG",
                    $"DPAPI Unprotect failed for device_guid.dat: {ex.GetType().Name}: {ex.Message}. Renaming to .corrupt.");
                try
                {
                    string corruptPath = path + ".corrupt";
                    if (File.Exists(corruptPath)) File.Delete(corruptPath);
                    File.Move(path, corruptPath);
                }
                catch (Exception renameEx)
                {
                    _logger.Log(LogLevel.ERROR, "DEVICE_DEBUG",
                        $"Failed to rename corrupt device_guid.dat: {renameEx.Message}");
                }
            }
        }

        string newGuid = Guid.NewGuid().ToString();
        _logger.Log(LogLevel.INFO, "DEVICE_DEBUG", $"Generated new GUID: {newGuid}");
        try
        {
            byte[] bytes = Encoding.UTF8.GetBytes(newGuid);
            byte[] protectedBytes = ProtectedData.Protect(bytes, null, DataProtectionScope.CurrentUser);
            File.WriteAllBytes(path, protectedBytes);
            _logger.Log(LogLevel.INFO, "DEVICE_DEBUG", $"Saved new GUID to disk successfully.");
        }
        catch (Exception ex)
        {
            _logger.Log(LogLevel.ERROR, "DEVICE_DEBUG",
                $"FAILED to save new GUID to disk: {ex.GetType().Name}: {ex.Message}. GUID will not persist across restarts.");
        }

        return newGuid;
    }

    public string GetDeviceName()
    {
        string path = Path.Combine(_storageDir, "device_name.dat");
        if (File.Exists(path))
        {
            try
            {
                byte[] protectedBytes = File.ReadAllBytes(path);
                byte[] decryptedBytes = ProtectedData.Unprotect(protectedBytes, null, DataProtectionScope.CurrentUser);
                return Encoding.UTF8.GetString(decryptedBytes);
            }
            catch { }
        }

        string defaultName = Environment.MachineName;
        try
        {
            byte[] bytes = Encoding.UTF8.GetBytes(defaultName);
            byte[] protectedBytes = ProtectedData.Protect(bytes, null, DataProtectionScope.CurrentUser);
            File.WriteAllBytes(path, protectedBytes);
        }
        catch { }

        return defaultName;
    }

    public void ClearSession()
    {
        if (Directory.Exists(_storageDir))
        {
            // Explicitly only delete session-scoped files.
            // device_guid.dat and device_name.dat are intentionally excluded —
            // device identity must survive logout and restart.
            var filesToDelete = new[] { "tokens.dat", "trusted_time.dat", "license.dat", "vpn_profile.dat" };
            foreach (var filename in filesToDelete)
            {
                string path = Path.Combine(_storageDir, filename);
                if (File.Exists(path))
                {
                    try { File.Delete(path); } catch { }
                }
            }
        }
    }
}
