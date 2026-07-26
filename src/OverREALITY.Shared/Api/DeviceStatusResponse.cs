using System;
using System.Text.Json.Serialization;

namespace OverREALITY.Shared.Api
{
    public class DeviceStatusResponse
    {
        [JsonPropertyName("active")]
        public bool Active { get; set; }

        [JsonPropertyName("reason")]
        public string? Reason { get; set; }

        [JsonPropertyName("server_time")]
        public DateTime ServerTime { get; set; }

        [JsonPropertyName("heartbeat_interval")]
        public int HeartbeatInterval { get; set; }

        [JsonPropertyName("heartbeat_jitter")]
        public int HeartbeatJitter { get; set; }
    }
}
