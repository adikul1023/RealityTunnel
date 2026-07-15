using System.Windows.Controls;
using RealityTunnel.OperationsConsole.ViewModels;

namespace RealityTunnel.OperationsConsole.Views
{
    public partial class UserDetailsPanel : UserControl
    {
        public UserDetailsPanel(UserDetailsViewModel viewModel)
        {
            InitializeComponent();
            DataContext = viewModel;
        }
    }
}
