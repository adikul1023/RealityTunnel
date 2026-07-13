using System;
using System.Text.Json.Serialization;

namespace RealityTunnel.Models;

public sealed class DeviceStatusResponse
{
    [JsonPropertyName("active")]
    public bool Active { get; init; }

    [JsonPropertyName("reason")]
    public string? Reason { get; init; }

    [JsonPropertyName("server_time")]
    public DateTime ServerTime { get; init; }

    [JsonPropertyName("heartbeat_interval")]
    public int HeartbeatInterval { get; init; } = 60;
}
