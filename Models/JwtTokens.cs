using System;

namespace RealityTunnel.Models;

public record JwtTokens(
    string AccessToken,
    string RefreshToken,
    DateTimeOffset ExpiresAt
);
