using System;
using RealityTunnel.Models;

namespace RealityTunnel.Services;

public class LicenseService
{
    private readonly SecureStorageService _storage;
    private LicenseBlob? _currentBlob;

    public LicenseService(SecureStorageService storage)
    {
        _storage = storage;
        _currentBlob = _storage.GetLicenseBlob();
    }

    public void UpdateLicenseBlob(LicenseBlob blob)
    {
        _currentBlob = blob;
        _storage.SaveLicenseBlob(blob);
    }

    public bool IsGracePeriodValid()
    {
        var now = DateTimeOffset.UtcNow;
        var lastTrusted = _storage.GetLastTrustedTimestamp();
        
        // Clock rollback detected
        if (lastTrusted.HasValue && now < lastTrusted.Value)
        {
            return false;
        }

        // Hard maximum offline window (72 hours)
        if (lastTrusted.HasValue && now > lastTrusted.Value.AddHours(72))
        {
            return false;
        }

        // Stub: Check signature and license expiry payload
        return true; 
    }

    public void VerifySignatureOffline()
    {
        // Stub: Validate Ed25519 or ECDSA signature of the payload using hardcoded public key
    }
}
