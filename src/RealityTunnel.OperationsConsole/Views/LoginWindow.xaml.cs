using System.Windows;
using Wpf.Ui.Controls;
using RealityTunnel.OperationsConsole.ViewModels;

namespace RealityTunnel.OperationsConsole.Views
{
    public partial class LoginWindow : FluentWindow
    {
        private readonly LoginViewModel _viewModel;

        public LoginWindow(LoginViewModel viewModel)
        {
            InitializeComponent();
            _viewModel = viewModel;
            DataContext = _viewModel;
        }

        private void PwdBox_PasswordChanged(object sender, RoutedEventArgs e)
        {
            if (sender is PasswordBox pwdBox)
            {
                _viewModel.Password = pwdBox.Password;
            }
        }
    }
}
