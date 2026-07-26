using System;
using System.Collections.Concurrent;
using Microsoft.Extensions.Logging;

namespace OverREALITY.UI.Services;

public class LogEntry
{
    public DateTime Timestamp { get; set; }
    public LogLevel LogLevel { get; set; }
    public string Message { get; set; } = string.Empty;
    public string Category { get; set; } = string.Empty;
}

public interface IInMemoryLogSink
{
    event EventHandler<LogEntry> LogReceived;
    void AddLog(LogEntry log);
}

public class InMemoryLogSink : IInMemoryLogSink
{
    public event EventHandler<LogEntry>? LogReceived;

    public void AddLog(LogEntry log)
    {
        LogReceived?.Invoke(this, log);
    }
}

public class UiLogger : ILogger
{
    private readonly string _categoryName;
    private readonly IInMemoryLogSink _logSink;

    public UiLogger(string categoryName, IInMemoryLogSink logSink)
    {
        _categoryName = categoryName;
        _logSink = logSink;
    }

    public IDisposable? BeginScope<TState>(TState state) where TState : notnull => null;

    public bool IsEnabled(LogLevel logLevel) => true;

    public void Log<TState>(LogLevel logLevel, EventId eventId, TState state, Exception? exception, Func<TState, Exception?, string> formatter)
    {
        if (!IsEnabled(logLevel)) return;

        var message = formatter(state, exception);
        if (exception != null)
        {
            message += $"\n{exception}";
        }

        var entry = new LogEntry
        {
            Timestamp = DateTime.Now,
            LogLevel = logLevel,
            Category = _categoryName,
            Message = message
        };

        _logSink.AddLog(entry);
    }
}

public class UiLoggerProvider : ILoggerProvider
{
    private readonly IInMemoryLogSink _logSink;

    public UiLoggerProvider(IInMemoryLogSink logSink)
    {
        _logSink = logSink;
    }

    public ILogger CreateLogger(string categoryName)
    {
        return new UiLogger(categoryName, _logSink);
    }

    public void Dispose() { }
}
