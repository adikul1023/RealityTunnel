using System.Text.Json;
using Microsoft.Extensions.Logging.Abstractions;
using OverREALITY.Configuration;
using OverREALITY.Shared.Api.Configuration;
using Xunit;

namespace OverREALITY.Tests.Configuration;

public class ConfigurationBuilderTests
{
    [Fact]
    public void Build_ProducesGoldenConfiguration()
    {
        var profile = new ServerProfileDto
        {
            Server = "node1.stealthy.co.in",
            Port = 443,
            Uuid = "b84558e8-dce2-4bb3-93f9-72213eebde18",
            PublicKey = "test_pub_key",
            ShortId = "12345678",
            Sni = "speedtest.net",
            Transport = "vless",
            Fingerprint = "chrome"
        };

        var builder = new ConfigurationBuilder(new SingboxTemplateProvider(), NullLogger<ConfigurationBuilder>.Instance);
        var result = builder.Build(profile);

        // Parse to check structure
        using var doc = JsonDocument.Parse(result.JsonConfig);
        var root = doc.RootElement;
        
        Assert.True(root.TryGetProperty("dns", out _), "DNS block should be present");
        
        var inbounds = root.GetProperty("inbounds");
        Assert.Equal(1, inbounds.GetArrayLength());
        
        var outbounds = root.GetProperty("outbounds");
        Assert.Equal(3, outbounds.GetArrayLength());
        
        var proxy = outbounds[0];
        Assert.Equal("", proxy.GetProperty("flow").GetString());
        Assert.Equal("", proxy.GetProperty("packet_encoding").GetString());
    }
}
