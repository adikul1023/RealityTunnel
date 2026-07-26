namespace OverREALITY.UI.Models;

public class ConnectionPresentationState
{
    public string Title { get; set; } = string.Empty;
    public string Subtitle { get; set; } = string.Empty;
    public bool IsBusy { get; set; }
    public bool CanConnect { get; set; }
    public bool CanDisconnect { get; set; }
    public string AccentColor { get; set; } = "DeepPurple";
}
