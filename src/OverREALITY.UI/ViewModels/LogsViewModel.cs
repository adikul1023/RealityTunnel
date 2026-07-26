using System;
using System.Collections.ObjectModel;
using CommunityToolkit.Mvvm.ComponentModel;
using OverREALITY.UI.Services;

namespace OverREALITY.UI.ViewModels;

public partial class LogsViewModel : ObservableObject, IDisposable
{
    private readonly IInMemoryLogSink _logSink;

    public ObservableCollection<LogEntry> Logs { get; } = new();

    private readonly IUiDispatcher _dispatcher;
    public LogsViewModel(IInMemoryLogSink logSink, IUiDispatcher dispatcher)
    {
        _logSink = logSink;
        _dispatcher = dispatcher;
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

    public void Dispose()
    {
        _logSink.LogReceived -= OnLogReceived;
    }
}
