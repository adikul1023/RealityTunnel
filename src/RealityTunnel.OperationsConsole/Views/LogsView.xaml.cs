using System.Windows.Controls;
using RealityTunnel.OperationsConsole.ViewModels;

namespace RealityTunnel.OperationsConsole.Views
{
    public partial class LogsView : UserControl
    {
        public LogsView(LogsViewModel viewModel)
        {
            InitializeComponent();
            DataContext = viewModel;
        }
    }
}
