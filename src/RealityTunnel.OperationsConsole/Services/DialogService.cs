using System.Threading.Tasks;
using System.Windows;

namespace RealityTunnel.OperationsConsole.Services
{
    public interface IDialogService
    {
        Task ShowErrorAsync(string title, string message);
        Task ShowInfoAsync(string title, string message);
        Task<bool> ShowConfirmationAsync(string title, string message, string confirmText = "Confirm", string cancelText = "Cancel");
    }

    public class DialogService : IDialogService
    {
        public async Task ShowErrorAsync(string title, string message)
        {
            await Application.Current.Dispatcher.InvokeAsync(() =>
            {
                System.Windows.MessageBox.Show(message, title, MessageBoxButton.OK, MessageBoxImage.Error);
            });
        }

        public async Task ShowInfoAsync(string title, string message)
        {
            await Application.Current.Dispatcher.InvokeAsync(() =>
            {
                System.Windows.MessageBox.Show(message, title, MessageBoxButton.OK, MessageBoxImage.Information);
            });
        }

        public async Task<bool> ShowConfirmationAsync(string title, string message, string confirmText = "Confirm", string cancelText = "Cancel")
        {
            return await Application.Current.Dispatcher.InvokeAsync(() =>
            {
                var res = System.Windows.MessageBox.Show(message, title, MessageBoxButton.YesNo, MessageBoxImage.Question);
                return res == MessageBoxResult.Yes;
            });
        }
    }
}
