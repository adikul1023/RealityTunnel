using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace RealityTunnel.Helper;

public class HelperLogger
{
    private readonly string _logDir;
    private readonly string _logFile;
    private readonly object _lock = new object();

    public HelperLogger()
    {
        string programData = Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData);
        _logDir = Path.Combine(programData, "RealityTunnel", "Helper");
        _logFile = Path.Combine(_logDir, "helper.log");

        try
        {
            if (!Directory.Exists(_logDir))
            {
                Directory.CreateDirectory(_logDir);
            }
        }
        catch { }
    }

    public void LogInfo(string message) => Log("INFO", message);
    public void LogWarn(string message) => Log("WARN", message);
    public void LogError(string message, Exception? ex = null) => Log("ERROR", $"{message} {(ex != null ? ex.ToString() : "")}");

    private void Log(string level, string message)
    {
        string formatted = $"[{DateTimeOffset.UtcNow:o}] [{level}] {message}";
        Console.WriteLine(formatted);

        lock (_lock)
        {
            try
            {
                File.AppendAllText(_logFile, formatted + Environment.NewLine);
            }
            catch { }
        }
    }

    public string[] GetLogTail(int lineCount = 100)
    {
        lock (_lock)
        {
            try
            {
                if (!File.Exists(_logFile)) return Array.Empty<string>();
                var lines = File.ReadAllLines(_logFile);
                return lines.Skip(Math.Max(0, lines.Length - lineCount)).ToArray();
            }
            catch
            {
                return new[] { "Failed to read helper log." };
            }
        }
    }
}
