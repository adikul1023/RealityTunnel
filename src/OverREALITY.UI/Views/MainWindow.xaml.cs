using System.Windows;
using OverREALITY.UI.ViewModels;

namespace OverREALITY.UI.Views;

public partial class MainWindow : Window
{
    public MainWindow(MainViewModel viewModel)
    {
        InitializeComponent();
        DataContext = viewModel;
    }
}
