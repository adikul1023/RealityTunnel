using OverREALITY.Shared.Models;

namespace OverREALITY.Shared.Interfaces;

public interface ISettingsService
{
    ClientSettings Settings { get; }
    void SaveSettings(ClientSettings settings);
}
