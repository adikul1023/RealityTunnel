using System;
using System.IO;
using Microsoft.Extensions.Logging;

namespace OverREALITY.Shared.Logging;

public class FileLoggerProvider : ILoggerProvider
{
    private readonly string _filePath;
    private static readonly object _lock = new();

    public FileLoggerProvider(string filePath)
    {
        _filePath = filePath;
        var dir = Path.GetDirectoryName(filePath);
        if (!string.IsNullOrEmpty(dir) && !Directory.Exists(dir))
        {
            Directory.CreateDirectory(dir);
        }
    }

    public ILogger CreateLogger(string categoryName) => new FileLogger(categoryName, _filePath);

    public void Dispose() { }

    private class FileLogger : ILogger
    {
        private readonly string _category;
        private readonly string _filePath;

        public FileLogger(string category, string filePath)
        {
            _category = category;
            _filePath = filePath;
        }

        public IDisposable? BeginScope<TState>(TState state) where TState : notnull => null;

        public bool IsEnabled(LogLevel logLevel) => true;

        public void Log<TState>(LogLevel logLevel, EventId eventId, TState state, Exception? exception, Func<TState, Exception?, string> formatter)
        {
            var line = $"[{DateTime.UtcNow:yyyy-MM-dd HH:mm:ss.fff}] [{logLevel}] [{_category}] {formatter(state, exception)}";
            if (exception != null)
            {
                line += Environment.NewLine + exception.ToString();
            }

            lock (_lock)
            {
                try
                {
                    File.AppendAllText(_filePath, line + Environment.NewLine);
                }
                catch { }
            }
        }
    }
}
