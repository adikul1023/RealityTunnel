using System.Text.Json;
using System.Text.Json.Serialization;
using OverREALITY.Shared.Api.Configuration;
using OverREALITY.Shared.Api.VpnRuntime;
using Xunit;

namespace OverREALITY.Tests.Core;

public class IpcSerializationTests
{
    [Fact]
    public void StartVpnRequest_Serialization_IsStable()
    {
        var request = new StartVpnRequest
        {
            Config = new VPNConfig
            {
                SchemaVersion = 1,
                JsonConfig = "{ \"test\": true }"
            }
        };

        var options = new JsonSerializerOptions 
        { 
            WriteIndented = false,
            DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull
        };

        var json = JsonSerializer.Serialize(request, options);

        // Golden JSON for IPC
        var expectedJson = "{\"config\":{\"SchemaVersion\":1,\"JsonConfig\":\"{ \\u0022test\\u0022: true }\"}}";
        
        // Asserting that Property Naming Policies or other global changes don't silently break IPC
        // Note: Default serialization (without camelCase policy) keeps pascal case by default unless overridden.
        // Let's check what the default serialization produces to ensure it's locked in.
        
        Assert.Equal(expectedJson, json);

        var deserialized = JsonSerializer.Deserialize<StartVpnRequest>(json, options);
        Assert.NotNull(deserialized);
        Assert.NotNull(deserialized!.Config);
        Assert.Equal(1, deserialized.Config.SchemaVersion);
        Assert.Equal("{ \"test\": true }", deserialized.Config.JsonConfig);
    }
}
