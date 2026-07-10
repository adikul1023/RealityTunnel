using System;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using RealityTunnel.Models;

namespace RealityTunnel.Services;

public class SecureStorageService
{
    private readonly string _storageDir;
    
    public SecureStorageService()
    {
        _storageDir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "OverREALITY", "Secure");
        if (!Directory.Exists(_storageDir))
        {
            Directory.CreateDirectory(_storageDir);
        }
    }

    public void SaveMasterToken(string token)
    {
        byte[] tokenBytes = Encoding.UTF8.GetBytes(token);
        try
        {
            byte[] protectedBytes = ProtectedData.Protect(tokenBytes, null, DataProtectionScope.CurrentUser);
            File.WriteAllBytes(Path.Combine(_storageDir, "master.dat"), protectedBytes);
        }
        finally
        {
            Array.Clear(tokenBytes, 0, tokenBytes.Length);
        }
    }

    /// <summary>
    /// Reads and decrypts the master token. The caller is responsible for clearing the returned char array!
    /// </summary>
    public char[]? GetMasterToken()
    {
        string path = Path.Combine(_storageDir, "master.dat");
        if (!File.Exists(path)) return null;

        byte[] protectedBytes = File.ReadAllBytes(path);
        byte[]? decryptedBytes = null;
        try
        {
            decryptedBytes = ProtectedData.Unprotect(protectedBytes, null, DataProtectionScope.CurrentUser);
            char[] tokenChars = Encoding.UTF8.GetChars(decryptedBytes);
            return tokenChars;
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
            return null;
        }
        finally
        {
            if (decryptedBytes != null)
            {
                Array.Clear(decryptedBytes, 0, decryptedBytes.Length);
            }
        }
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

        string newGuid = Guid.NewGuid().ToString();
        try
        {
            byte[] bytes = Encoding.UTF8.GetBytes(newGuid);
            byte[] protectedBytes = ProtectedData.Protect(bytes, null, DataProtectionScope.CurrentUser);
            File.WriteAllBytes(path, protectedBytes);
        }
        catch { }
        
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

    public void ClearAll()
    {
        if (Directory.Exists(_storageDir))
        {
            foreach (var file in Directory.GetFiles(_storageDir))
            {
                File.Delete(file);
            }
        }
    }
}
