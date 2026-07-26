using System;
using System.Threading.Tasks;
using System.Windows;

namespace OverREALITY.UI.Services;

public class WpfUiDispatcher : IUiDispatcher
{
    public void Invoke(Action action)
    {
        Application.Current?.Dispatcher?.Invoke(action);
    }

    public Task InvokeAsync(Action action)
    {
        return Application.Current?.Dispatcher?.InvokeAsync(action).Task ?? Task.CompletedTask;
    }
}
