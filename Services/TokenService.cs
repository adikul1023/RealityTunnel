using System;
using RealityTunnel.Models;

namespace RealityTunnel.Services;

public class TokenService
{
    private readonly SecureStorageService _storage;
    private JwtTokens? _currentTokens;

    public TokenService(SecureStorageService storage)
    {
        _storage = storage;
        _currentTokens = _storage.GetJwtTokens();
    }

    public JwtTokens? GetCurrentTokens() => _currentTokens;
    public JwtTokens? CurrentTokens => _currentTokens;

    public SessionState GetCurrentState()
    {
        if (_currentTokens == null)
        {
            return SessionState.Offline; 
        }

        if (DateTimeOffset.UtcNow >= _currentTokens.ExpiresAt)
        {
            return SessionState.Expired;
        }

        return SessionState.Authenticated;
    }

    public void UpdateTokens(JwtTokens tokens)
    {
        _currentTokens = tokens;
        _storage.SaveJwtTokens(tokens);
    }

    public void UpdateTokensInMemoryOnly(JwtTokens tokens)
    {
        _currentTokens = tokens;
    }

    public void ClearTokens()
    {
        _currentTokens = null;
        _storage.ClearAll(); // For now, clearing all on token clear
    }

    // Handles the replay detection flow outlined in the architecture
    public void HandleReplayDetected()
    {
        ClearTokens();
        // Event or callback to UI to force login could go here
    }
}
