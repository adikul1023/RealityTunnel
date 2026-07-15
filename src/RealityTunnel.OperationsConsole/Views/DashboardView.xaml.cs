using System.Windows.Controls;
using RealityTunnel.OperationsConsole.ViewModels;

namespace RealityTunnel.OperationsConsole.Views
{
    public partial class DashboardView : UserControl
    {
        public DashboardView(DashboardViewModel viewModel)
        {
            InitializeComponent();
            DataContext = viewModel;
        }
    }
}
