using System.Windows.Controls;
using RealityTunnel.OperationsConsole.ViewModels;

namespace RealityTunnel.OperationsConsole.Views
{
    public partial class UsersView : UserControl
    {
        public UsersView(UsersViewModel viewModel)
        {
            InitializeComponent();
            DataContext = viewModel;
        }
    }
}
