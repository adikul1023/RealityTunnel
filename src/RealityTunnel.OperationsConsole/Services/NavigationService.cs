using System;

namespace RealityTunnel.OperationsConsole.Services
{
    public interface INavigationService
    {
        event Action<string, object?>? OnNavigate;
        event Action? OnNavigateToLogin;
        event Action? OnNavigateToMain;

        void NavigateTo(string viewKey, object? parameter = null);
        void ShowLoginWindow();
        void ShowMainWindow();
    }

    public class NavigationService : INavigationService
    {
        public event Action<string, object?>? OnNavigate;
        public event Action? OnNavigateToLogin;
        public event Action? OnNavigateToMain;

        public void NavigateTo(string viewKey, object? parameter = null)
        {
            OnNavigate?.Invoke(viewKey, parameter);
        }

        public void ShowLoginWindow()
        {
            OnNavigateToLogin?.Invoke();
        }

        public void ShowMainWindow()
        {
            OnNavigateToMain?.Invoke();
        }
    }
}
