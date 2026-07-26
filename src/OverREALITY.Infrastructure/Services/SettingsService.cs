using System.IO;
using System.Text.Json;
using OverREALITY.Shared.Interfaces;
using OverREALITY.Shared.Models;

namespace OverREALITY.Infrastructure.Services;

public class SettingsService : ISettingsService
{
    private readonly string _settingsFilePath;
    private ClientSettings _settings;

    public SettingsService()
    {
        _settingsFilePath = Path.Combine(Path.GetTempPath(), "OverREALITY", "settings.json");
        var directory = Path.GetDirectoryName(_settingsFilePath);
        if (directory != null && !Directory.Exists(directory))
        {
            Directory.CreateDirectory(directory);
        }

        _settings = LoadFromFile();
    }

    public ClientSettings Settings => _settings;

    public void SaveSettings(ClientSettings settings)
    {
        _settings = settings;
        var json = JsonSerializer.Serialize(_settings, new JsonSerializerOptions { WriteIndented = true });
        File.WriteAllText(_settingsFilePath, json);
    }

    private ClientSettings LoadFromFile()
    {
        if (File.Exists(_settingsFilePath))
        {
            try
            {
                var json = File.ReadAllText(_settingsFilePath);
                return JsonSerializer.Deserialize<ClientSettings>(json) ?? new ClientSettings();
            }
            catch
            {
                return new ClientSettings();
            }
        }
        return new ClientSettings();
    }
}
