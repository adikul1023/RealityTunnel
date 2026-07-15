using System.Windows.Controls;
using RealityTunnel.OperationsConsole.ViewModels;

namespace RealityTunnel.OperationsConsole.Views
{
    public partial class SubscriptionsView : UserControl
    {
        public SubscriptionsView(SubscriptionsViewModel viewModel)
        {
            InitializeComponent();
            DataContext = viewModel;
        }
    }
}
