using System.Threading.Tasks;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using OverREALITY.Shared.Interfaces;
using OverREALITY.UI.Services;

namespace OverREALITY.UI.ViewModels;

public partial class LoginViewModel : ObservableObject
{
    private readonly IAuthService _authService;
    private readonly INavigationService _navigationService;

    [ObservableProperty]
    private string _accountKey = string.Empty;

    [ObservableProperty]
    private string _errorMessage = string.Empty;

    [ObservableProperty]
    private bool _isBusy;

    public LoginViewModel(IAuthService authService, INavigationService navigationService)
    {
        _authService = authService;
        _navigationService = navigationService;
    }

    [RelayCommand]
    private async Task LoginAsync()
    {
        var key = AccountKey?.Trim() ?? string.Empty;
        var parts = key.Split(':');

        if (parts.Length != 2 || string.IsNullOrWhiteSpace(parts[0]) || string.IsNullOrWhiteSpace(parts[1]))
        {
            ErrorMessage = "Invalid Account Key format. Expected format: AccountID:MasterToken";
            return;
        }

        ErrorMessage = string.Empty;
        IsBusy = true;

        var result = await _authService.LoginAsync(parts[0].Trim(), parts[1].Trim());

        IsBusy = false;

        if (result.IsSuccess)
        {
            _navigationService.NavigateTo<DashboardViewModel>();
        }
        else
        {
            ErrorMessage = result.Error?.Message ?? "Authentication failed.";
        }
    }
}

