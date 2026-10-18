using System;
using System.Collections.ObjectModel;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using Microsoft.Extensions.Logging;
using OverREALITY.UI.Services;

namespace OverREALITY.UI.ViewModels;

public partial class LogsViewModel : ObservableObject, IDisposable
{
    private readonly IInMemoryLogSink _logSink;
    private readonly IUiDispatcher _dispatcher;
    private readonly CancellationTokenSource _cts = new();
    private long _lastHelperLogPosition;

    public ObservableCollection<LogEntry> Logs { get; } = new();

    [ObservableProperty]
    private string _statusMessage = string.Empty;

    public LogsViewModel(IInMemoryLogSink logSink, IUiDispatcher dispatcher)
    {
        _logSink = logSink;
        _dispatcher = dispatcher;

        foreach (var log in _logSink.GetRecentLogs())
        {
            Logs.Add(log);
        }

        _logSink.LogReceived += OnLogReceived;

        // Tail helper log file from ProgramData in the background
        _ = Task.Run(() => TailHelperLogAsync(_cts.Token));
    }

    private void OnLogReceived(object? sender, LogEntry e)
    {
        _dispatcher.Invoke(() =>
        {
            Logs.Add(e);
            if (Logs.Count > 1500)
            {
                Logs.RemoveAt(0);
            }
        });
    }

    private async Task TailHelperLogAsync(CancellationToken cancellationToken)
    {
        var helperLogPath = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData), "OverREALITY", "logs", "helper.log");

        while (!cancellationToken.IsCancellationRequested)
        {
            try
            {
                if (File.Exists(helperLogPath))
                {
                    using var stream = new FileStream(helperLogPath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite);
                    if (stream.Length < _lastHelperLogPosition)
                    {
                        _lastHelperLogPosition = 0;
                    }

                    if (stream.Length > _lastHelperLogPosition)
                    {
                        stream.Seek(_lastHelperLogPosition, SeekOrigin.Begin);
                        using var reader = new StreamReader(stream, Encoding.UTF8);
                        string? line;
                        while ((line = await reader.ReadLineAsync(cancellationToken)) != null)
                        {
                            if (!string.IsNullOrWhiteSpace(line))
                            {
                                var entry = ParseLogLine(line);
                                _dispatcher.Invoke(() =>
                                {
                                    Logs.Add(entry);
                                    if (Logs.Count > 1500)
                                    {
                                        Logs.RemoveAt(0);
                                    }
                                });
                            }
                        }
                        _lastHelperLogPosition = stream.Position;
                    }
                }
            }
            catch
            {
                // File access conflict or not yet created, retry on next loop
            }

            try
            {
                await Task.Delay(1000, cancellationToken);
            }
            catch (OperationCanceledException)
            {
                break;
            }
        }
    }

    private static LogEntry ParseLogLine(string line)
    {
        try
        {
            if (line.StartsWith("["))
            {
                var parts = line.Split(new[] { "] [" }, 3, StringSplitOptions.None);
                if (parts.Length >= 3)
                {
                    var timeStr = parts[0].TrimStart('[');
                    var levelStr = parts[1];
                    var remainder = parts[2];
                    var catEnd = remainder.IndexOf(']');
                    if (catEnd > 0)
                    {
                        var category = remainder.Substring(0, catEnd);
                        var message = remainder.Substring(catEnd + 1).Trim();
                        DateTime.TryParse(timeStr, out var ts);
                        Enum.TryParse<LogLevel>(levelStr, true, out var lvl);

                        return new LogEntry
                        {
                            Timestamp = ts == default ? DateTime.Now : ts,
                            LogLevel = lvl,
                            Category = category,
                            Message = message
                        };
                    }
                }
            }
        }
        catch { }

        return new LogEntry
        {
            Timestamp = DateTime.Now,
            LogLevel = LogLevel.Information,
            Category = "Helper",
            Message = line
        };
    }

    [RelayCommand]
    private void CopyLogs()
    {
        try
        {
            var sb = new StringBuilder();
            foreach (var log in Logs)
            {
                sb.AppendLine($"[{log.Timestamp:yyyy-MM-dd HH:mm:ss.fff}] [{log.LogLevel}] [{log.Category}] {log.Message}");
            }

            var text = sb.Length > 0 ? sb.ToString() : "No logs available.";
            Clipboard.SetText(text);
            StatusMessage = "Logs copied to clipboard!";
            _ = ClearStatusAfterDelayAsync();
        }
        catch (Exception ex)
        {
            StatusMessage = $"Copy failed: {ex.Message}";
        }
    }

    [RelayCommand]
    private void OpenLogsFolder()
    {
        try
        {
            var logDir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData), "OverREALITY", "logs");
            if (!Directory.Exists(logDir))
            {
                Directory.CreateDirectory(logDir);
            }
            Process.Start(new ProcessStartInfo
            {
                FileName = logDir,
                UseShellExecute = true
            });
        }
        catch (Exception ex)
        {
            StatusMessage = $"Open folder failed: {ex.Message}";
        }
    }

    [RelayCommand]
    private void ClearLogs()
    {
        Logs.Clear();
        StatusMessage = "Logs display cleared.";
        _ = ClearStatusAfterDelayAsync();
    }

    private async Task ClearStatusAfterDelayAsync()
    {
        await Task.Delay(3000);
        StatusMessage = string.Empty;
    }

    public void Dispose()
    {
        _cts.Cancel();
        _cts.Dispose();
        _logSink.LogReceived -= OnLogReceived;
    }
}
