namespace OverREALITY.Shared.Contracts;

public class StartVpnResponse
{
    public bool Success { get; set; }
    public string? Error { get; set; }
    public int? Pid { get; set; }
    public string? InterfaceName { get; set; }
}
