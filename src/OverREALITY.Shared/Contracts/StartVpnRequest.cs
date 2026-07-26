using System;

namespace OverREALITY.Shared.Contracts;

public class StartVpnRequest
{
    public string ConfigurationJson { get; set; } = string.Empty;
    public bool KillSwitch { get; set; }
    public bool EnableIPv6 { get; set; }
    public string DnsMode { get; set; } = string.Empty;
    public DateTime Timestamp { get; set; }
}
