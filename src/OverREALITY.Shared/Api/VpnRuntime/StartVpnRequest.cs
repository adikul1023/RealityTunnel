using System.Text.Json.Serialization;
using OverREALITY.Shared.Api.Configuration;

namespace OverREALITY.Shared.Api.VpnRuntime;

public class StartVpnRequest
{
    [JsonPropertyName("config")]
    public VPNConfig Config { get; set; } = new VPNConfig();
}
