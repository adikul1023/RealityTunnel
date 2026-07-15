using System.Windows.Controls;
using RealityTunnel.OperationsConsole.ViewModels;

namespace RealityTunnel.OperationsConsole.Views
{
    public partial class PaymentsView : UserControl
    {
        public PaymentsView(PaymentsViewModel viewModel)
        {
            InitializeComponent();
            DataContext = viewModel;
        }
    }
}
