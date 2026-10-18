using System;
using System.Collections.ObjectModel;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Threading.Tasks;
using System.Windows;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using OverREALITY.UI.Services;

namespace OverREALITY.UI.ViewModels;

public partial class LogsViewModel : ObservableObject, IDisposable
{
    private readonly IInMemoryLogSink _logSink;
    private readonly IUiDispatcher _dispatcher;

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
    }

    private void OnLogReceived(object? sender, LogEntry e)
    {
        _dispatcher.InvokeAsync(() =>
        {
            Logs.Add(e);
            if (Logs.Count > 1000)
            {
                Logs.RemoveAt(0);
            }
        });
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
            var uiLogDir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "OverREALITY", "logs");
            if (!Directory.Exists(uiLogDir))
            {
                Directory.CreateDirectory(uiLogDir);
            }
            Process.Start(new ProcessStartInfo
            {
                FileName = uiLogDir,
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
        _logSink.LogReceived -= OnLogReceived;
    }
}
