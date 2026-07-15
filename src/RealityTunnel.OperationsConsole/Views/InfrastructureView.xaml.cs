using System.Windows.Controls;
using RealityTunnel.OperationsConsole.ViewModels;

namespace RealityTunnel.OperationsConsole.Views
{
    public partial class InfrastructureView : UserControl
    {
        public InfrastructureView(InfrastructureViewModel viewModel)
        {
            InitializeComponent();
            DataContext = viewModel;
        }
    }
}
