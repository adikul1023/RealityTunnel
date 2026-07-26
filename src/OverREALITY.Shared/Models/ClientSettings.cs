namespace OverREALITY.Shared.Models;

public class ClientSettings
{
    public bool AutoConnect { get; set; }
    public bool StartWithWindows { get; set; }
    public string Theme { get; set; } = "Light";
    public string Environment { get; set; } = "Production";
    public string LoggingLevel { get; set; } = "Information";
}
