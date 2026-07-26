using System.Collections.Generic;
using System.Text.Json;
using System.Text.Json.Serialization;
using Microsoft.Extensions.Logging;
using OverREALITY.Configuration.Models;
using OverREALITY.Shared.Api.Configuration;
using OverREALITY.Shared.Interfaces;

namespace OverREALITY.Configuration;

public class ConfigurationBuilder : IConfigurationBuilder
{
    private readonly ISingboxTemplateProvider _templateProvider;
    private readonly Microsoft.Extensions.Logging.ILogger<ConfigurationBuilder> _logger;

    public ConfigurationBuilder(ISingboxTemplateProvider templateProvider, Microsoft.Extensions.Logging.ILogger<ConfigurationBuilder> logger)
    {
        _templateProvider = templateProvider;
        _logger = logger;
    }

    public VPNConfig Build(ServerProfileDto profile)
    {
        var configObj = _templateProvider.GetBaseTemplate();

        configObj.Outbounds = new List<OutboundConfig>
        {
            new OutboundConfig
            {
                Type = "vless", // Sing-box expects "vless" for VLESS connections
                Tag = "proxy",
                Server = profile.Server,
                ServerPort = profile.Port,
                Uuid = profile.Uuid,
                Flow = "",
                PacketEncoding = "",
                Tls = new TlsConfig
                {
                    Enabled = true,
                    ServerName = "dl.google.com",
                    Utls = new UtlsConfig
                    {
                        Enabled = true,
                        Fingerprint = profile.Fingerprint
                    },
                    Reality = new RealityConfig
                    {
                        Enabled = true,
                        PublicKey = profile.PublicKey,
                        ShortId = profile.ShortId
                    }
                }
            },
            new OutboundConfig { Type = "direct", Tag = "direct" },
            new OutboundConfig { Type = "block", Tag = "block" }
        };

        var options = new JsonSerializerOptions 
        { 
            WriteIndented = true,
            DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull
        };
        var json = JsonSerializer.Serialize(configObj, options);
        _logger.LogInformation("Generated sing-box configuration: {JsonConfig}", json);
        return new VPNConfig { JsonConfig = json };
    }
}
