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

    // Ephemeral in-memory credentials held only during an active 2FA challenge
    private string? _challengeAccountId;
    private string? _challengeMasterToken;

    [ObservableProperty]
    private string _accountKey = string.Empty;

    [ObservableProperty]
    private string _twoFaCode = string.Empty;

    [ObservableProperty]
    private bool _is2FaRequired;

    [ObservableProperty]
    private string _errorMessage = string.Empty;

    [ObservableProperty]
    [NotifyCanExecuteChangedFor(nameof(LoginCommand))]
    [NotifyCanExecuteChangedFor(nameof(Verify2FaCommand))]
    [NotifyCanExecuteChangedFor(nameof(Cancel2FaCommand))]
    private bool _isBusy;

    public LoginViewModel(IAuthService authService, INavigationService navigationService)
    {
        _authService = authService;
        _navigationService = navigationService;
    }

    private bool CanAuthenticate() => !IsBusy;

    [RelayCommand(CanExecute = nameof(CanAuthenticate))]
    private async Task LoginAsync()
    {
        if (IsBusy) return;

        var key = AccountKey?.Trim() ?? string.Empty;
        var parts = key.Split(':', 2);

        if (parts.Length != 2 || string.IsNullOrWhiteSpace(parts[0]) || string.IsNullOrWhiteSpace(parts[1]))
        {
            ErrorMessage = "Invalid Account Key format. Expected format: AccountID:MasterToken";
            return;
        }

        var accountId = parts[0].Trim();
        var masterToken = parts[1].Trim();

        ErrorMessage = string.Empty;
        IsBusy = true;

        var result = await _authService.LoginAsync(accountId, masterToken);

        IsBusy = false;

        if (result.IsSuccess)
        {
            ClearChallengeState();
            _navigationService.NavigateTo<DashboardViewModel>();
        }
        else if (result.Error?.Requires2Fa == true || result.Error?.Code == "REQUIRES_2FA")
        {
            // Transition to 2FA challenge state
            _challengeAccountId = accountId;
            _challengeMasterToken = masterToken;
            TwoFaCode = string.Empty;
            Is2FaRequired = true;
            ErrorMessage = string.Empty;
        }
        else
        {
            ErrorMessage = result.Error?.Message ?? "Authentication failed.";
        }
    }

    [RelayCommand(CanExecute = nameof(CanAuthenticate))]
    private async Task Verify2FaAsync()
    {
        if (IsBusy) return;

        var code = TwoFaCode?.Trim() ?? string.Empty;
        if (string.IsNullOrWhiteSpace(code))
        {
            ErrorMessage = "Please enter your 2FA code or backup code.";
            return;
        }

        if (string.IsNullOrEmpty(_challengeAccountId) || string.IsNullOrEmpty(_challengeMasterToken))
        {
            ErrorMessage = "Login session expired. Please re-enter your Account Key.";
            Cancel2Fa();
            return;
        }

        ErrorMessage = string.Empty;
        IsBusy = true;

        var result = await _authService.LoginAsync(_challengeAccountId, _challengeMasterToken, code);

        IsBusy = false;

        if (result.IsSuccess)
        {
            ClearChallengeState();
            _navigationService.NavigateTo<DashboardViewModel>();
        }
        else
        {
            // Invalid OTP or expired: keep OTP screen open for retry
            ErrorMessage = result.Error?.Message ?? "Invalid two-factor authentication code.";
        }
    }

    [RelayCommand(CanExecute = nameof(CanAuthenticate))]
    private void Cancel2Fa()
    {
        if (IsBusy) return;

        ClearChallengeState();
        Is2FaRequired = false;
        ErrorMessage = string.Empty;
    }

    private void ClearChallengeState()
    {
        _challengeAccountId = null;
        _challengeMasterToken = null;
        TwoFaCode = string.Empty;
        Is2FaRequired = false;
    }
}
