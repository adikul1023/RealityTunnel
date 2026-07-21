using System;
using System.IO;
using System.Text.Json;
using RealityTunnel.Models;

namespace RealityTunnel;

public class AppSettings
{
    public int WindowWidth { get; set; } = 1050;
    public int WindowHeight { get; set; } = 720;
    public int? WindowX { get; set; }
    public int? WindowY { get; set; }
    public string Theme { get; set; } = "System";
    public VpnBackendKind VpnBackend { get; set; } = VpnBackendKind.InProcess;
    private static string FilePath =>
        Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "OverREALITY",
            "settings.json");

    public static AppSettings Load()
    {
        try
        {
            if (File.Exists(FilePath))
                return JsonSerializer.Deserialize<AppSettings>(File.ReadAllText(FilePath)) ?? new();
        }
        catch { }
        return new();
    }

    public void Save()
    {
        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(FilePath)!);
            File.WriteAllText(FilePath, JsonSerializer.Serialize(this));
        }
        catch { }
    }
}
