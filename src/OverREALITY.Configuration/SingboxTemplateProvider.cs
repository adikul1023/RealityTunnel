using System.Collections.Generic;
using OverREALITY.Configuration.Models;

namespace OverREALITY.Configuration;

public class SingboxTemplateProvider : ISingboxTemplateProvider
{
    public SingboxConfig GetBaseTemplate()
    {
        return new SingboxConfig
        {
            Log = new LogConfig { Level = "debug" },
            Dns = new DnsConfig
            {
                Servers = new List<DnsServerConfig>
                {
                    new DnsServerConfig
                    {
                        Type = "udp",
                        Tag = "remote",
                        Server = "8.8.8.8",
                        ServerPort = 53
                    },
                    new DnsServerConfig
                    {
                        Type = "udp",
                        Tag = "remote-fallback",
                        Server = "9.9.9.9",
                        ServerPort = 53
                    },
                    new DnsServerConfig
                    {
                        Type = "local",
                        Tag = "local"
                    }
                },
                Final = "remote",
                Strategy = "ipv4_only"
            },
            Inbounds = new List<InboundConfig>
            {
                new InboundConfig
                {
                    Type = "tun",
                    Tag = "tun-in",
                    InterfaceName = "singbox_tun",
                    Stack = "mixed",
                    Address = new List<string> { "10.0.85.2/24", "fdfe:dcba:9876::1/126" },
                    AutoRoute = true,
                    StrictRoute = true,
                    Sniff = true,
                    SniffOverrideDestination = true
                }
            },
            Route = new RouteConfig
            {
                Rules = new List<RouteRuleConfig>
                {
                    new RouteRuleConfig { Port = new List<int> { 53 }, Action = "hijack-dns" },
                    new RouteRuleConfig { IpVersion = 6, Outbound = "block" },
                    new RouteRuleConfig { IpIsPrivate = true, Outbound = "direct" },
                    new RouteRuleConfig { IpCidr = new List<string> { "8.8.8.8/32", "9.9.9.9/32" }, Outbound = "direct" }
                },
                AutoDetectInterface = true,
                Final = "proxy",
                DefaultDomainResolver = "remote"
            }
        };
    }
}
