using System.Windows;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using OverREALITY.Shared.Interfaces;

namespace OverREALITY.UI.ViewModels;

public partial class TrayViewModel : ObservableObject
{
    private readonly IConnectionService _connectionService;

    public TrayViewModel(IConnectionService connectionService)
    {
        _connectionService = connectionService;
    }

    [RelayCommand]
    private void ShowWindow()
    {
        Application.Current.MainWindow?.Show();
        Application.Current.MainWindow?.Activate();
    }

    [RelayCommand]
    private void HideWindow()
    {
        Application.Current.MainWindow?.Hide();
    }

    [RelayCommand]
    private async Task ConnectAsync()
    {
        await _connectionService.ConnectAsync();
    }

    [RelayCommand]
    private async Task DisconnectAsync()
    {
        await _connectionService.DisconnectAsync();
    }

    [RelayCommand]
    private void ExitApplication()
    {
        Application.Current.Shutdown();
    }
}
