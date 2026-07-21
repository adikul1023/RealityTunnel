using System.Text.Json.Serialization;

namespace RealityTunnel.Models;

[JsonConverter(typeof(JsonStringEnumConverter))]
public enum VpnBackendKind
{
    InProcess,
    NamedPipe
}
