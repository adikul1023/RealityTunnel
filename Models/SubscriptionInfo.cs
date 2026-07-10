using System;

namespace RealityTunnel.Models;

public record SubscriptionInfo(
    string Status,
    DateTimeOffset ExpiresAt
);
