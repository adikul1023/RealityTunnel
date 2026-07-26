using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace OverREALITY.Configuration.Models;

public class SingboxConfig
{
    [JsonPropertyName("log")]
    public LogConfig Log { get; set; } = new LogConfig();

    [JsonPropertyName("dns")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public DnsConfig? Dns { get; set; }

    [JsonPropertyName("inbounds")]
    public List<InboundConfig> Inbounds { get; set; } = new List<InboundConfig>();

    [JsonPropertyName("outbounds")]
    public List<OutboundConfig> Outbounds { get; set; } = new List<OutboundConfig>();

    [JsonPropertyName("route")]
    public RouteConfig Route { get; set; } = new RouteConfig();
}

public class LogConfig
{
    [JsonPropertyName("level")]
    public string Level { get; set; } = "info";
}

public class DnsConfig
{
    [JsonPropertyName("servers")]
    public List<DnsServerConfig> Servers { get; set; } = new List<DnsServerConfig>();

    [JsonPropertyName("rules")]
    public List<DnsRuleConfig> Rules { get; set; } = new List<DnsRuleConfig>();

    [JsonPropertyName("final")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public string? Final { get; set; }

    [JsonPropertyName("strategy")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public string? Strategy { get; set; }
}

public class DnsServerConfig
{
    [JsonPropertyName("type")]
    public string Type { get; set; } = string.Empty;

    [JsonPropertyName("tag")]
    public string Tag { get; set; } = string.Empty;

    [JsonPropertyName("server")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public string? Server { get; set; }

    [JsonPropertyName("server_port")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public int? ServerPort { get; set; }

    [JsonPropertyName("detour")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public string? Detour { get; set; }
}

public class DnsRuleConfig
{
    [JsonPropertyName("outbound")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public string? Outbound { get; set; }

    [JsonPropertyName("server")]
    public string Server { get; set; } = string.Empty;
}

public class InboundConfig
{
    [JsonPropertyName("type")]
    public string Type { get; set; } = string.Empty;

    [JsonPropertyName("tag")]
    public string Tag { get; set; } = string.Empty;

    [JsonPropertyName("interface_name")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public string? InterfaceName { get; set; }

    [JsonPropertyName("stack")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public string? Stack { get; set; }

    [JsonPropertyName("address")]
    public List<string> Address { get; set; } = new List<string>();

    [JsonPropertyName("auto_route")]
    public bool AutoRoute { get; set; }

    [JsonPropertyName("strict_route")]
    public bool StrictRoute { get; set; }

    [JsonPropertyName("sniff")]
    public bool Sniff { get; set; }

    [JsonPropertyName("sniff_override_destination")]
    public bool SniffOverrideDestination { get; set; }
}

public class OutboundConfig
{
    [JsonPropertyName("type")]
    public string Type { get; set; } = string.Empty;

    [JsonPropertyName("tag")]
    public string Tag { get; set; } = string.Empty;

    [JsonPropertyName("server")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public string? Server { get; set; }

    [JsonPropertyName("server_port")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public int? ServerPort { get; set; }

    [JsonPropertyName("uuid")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public string? Uuid { get; set; }

    [JsonPropertyName("flow")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public string? Flow { get; set; }

    [JsonPropertyName("tls")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public TlsConfig? Tls { get; set; }

    [JsonPropertyName("packet_encoding")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public string? PacketEncoding { get; set; }
}

public class TlsConfig
{
    [JsonPropertyName("enabled")]
    public bool Enabled { get; set; }

    [JsonPropertyName("server_name")]
    public string ServerName { get; set; } = string.Empty;

    [JsonPropertyName("alpn")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public List<string>? Alpn { get; set; }

    [JsonPropertyName("utls")]
    public UtlsConfig Utls { get; set; } = new UtlsConfig();

    [JsonPropertyName("reality")]
    public RealityConfig Reality { get; set; } = new RealityConfig();
}

public class UtlsConfig
{
    [JsonPropertyName("enabled")]
    public bool Enabled { get; set; }

    [JsonPropertyName("fingerprint")]
    public string Fingerprint { get; set; } = string.Empty;
}

public class RealityConfig
{
    [JsonPropertyName("enabled")]
    public bool Enabled { get; set; }

    [JsonPropertyName("public_key")]
    public string PublicKey { get; set; } = string.Empty;

    [JsonPropertyName("short_id")]
    public string ShortId { get; set; } = string.Empty;
}

public class RouteConfig
{
    [JsonPropertyName("rules")]
    public List<RouteRuleConfig> Rules { get; set; } = new List<RouteRuleConfig>();

    [JsonPropertyName("auto_detect_interface")]
    public bool AutoDetectInterface { get; set; }

    [JsonPropertyName("final")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public string? Final { get; set; }

    [JsonPropertyName("default_domain_resolver")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public string? DefaultDomainResolver { get; set; }
}

public class RouteRuleConfig
{
    [JsonPropertyName("protocol")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public string? Protocol { get; set; }

    [JsonPropertyName("ip_is_private")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public bool? IpIsPrivate { get; set; }

    [JsonPropertyName("ip_version")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public int? IpVersion { get; set; }

    [JsonPropertyName("ip_cidr")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public List<string>? IpCidr { get; set; }

    [JsonPropertyName("port")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public List<int>? Port { get; set; }

    [JsonPropertyName("action")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public string? Action { get; set; }

    [JsonPropertyName("outbound")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public string? Outbound { get; set; }
}
