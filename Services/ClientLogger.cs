using System;
using System.IO;
using System.Text;

namespace RealityTunnel.Services;

public enum LogLevel
{
    INFO,
    WARN,
    ERROR
}

public class ClientLogger
{
    private readonly string _logDir;
    private readonly string _logFile;
    private readonly object _lock = new object();
    private readonly string _sessionId;

    public ClientLogger()
    {
        _logDir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "OverREALITY", "Logs");
        if (!Directory.Exists(_logDir))
        {
            Directory.CreateDirectory(_logDir);
        }
        _logFile = Path.Combine(_logDir, "client.log");
        _sessionId = Guid.NewGuid().ToString("N").Substring(0, 8).ToUpperInvariant();
    }

    public string SessionId => _sessionId;

    public void Log(LogLevel level, string category, string message, string? requestId = null)
    {
        string reqId = requestId ?? Guid.NewGuid().ToString("N").Substring(0, 8).ToUpperInvariant();
        string levelStr = level switch
        {
            LogLevel.INFO => "INFO ",
            LogLevel.WARN => "WARN ",
            LogLevel.ERROR => "ERROR",
            _ => "INFO "
        };

        string timestamp = DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ");
        string sanitizedMessage = SanitizeMessage(message);
        string logLine = $"{timestamp} [{levelStr}] [{category}] session={_sessionId} request={reqId} {sanitizedMessage}";

        lock (_lock)
        {
            try
            {
                RollLogIfNeeded();
                File.AppendAllText(_logFile, logLine + Environment.NewLine, Encoding.UTF8);
            }
            catch
            {
                // Never crash application due to local filesystem logging failures
            }
        }
    }

    private void RollLogIfNeeded()
    {
        if (File.Exists(_logFile))
        {
            var info = new FileInfo(_logFile);
            if (info.Length >= 1024 * 1024) // 1MB
            {
                string backup = Path.Combine(_logDir, "client.log.1");
                if (File.Exists(backup))
                {
                    File.Delete(backup);
                }
                File.Move(_logFile, backup);
            }
        }
    }

    private static string SanitizeMessage(string input)
    {
        if (string.IsNullOrEmpty(input)) return input;
        var sanitized = System.Text.RegularExpressions.Regex.Replace(input, @"ey[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}", "[REDACTED_JWT]");
        sanitized = System.Text.RegularExpressions.Regex.Replace(sanitized, @"(?i)exchange_token=[^&\s]+", "exchange_token=[REDACTED]");
        sanitized = System.Text.RegularExpressions.Regex.Replace(sanitized, @"(?i)Bearer\s+[A-Za-z0-9_\-\.]+", "Bearer [REDACTED]");
        return sanitized;
    }
}
