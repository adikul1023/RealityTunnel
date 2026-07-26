using System;
using System.Threading.Tasks;

namespace OverREALITY.UI.Services;

public interface IUiDispatcher
{
    void Invoke(Action action);
    Task InvokeAsync(Action action);
}
