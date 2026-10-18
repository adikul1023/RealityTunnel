using System.Threading;
using System.Threading.Tasks;
using Moq;
using OverREALITY.Shared.Api.Authentication;
using OverREALITY.Shared.Errors;
using OverREALITY.Shared.Interfaces;
using OverREALITY.UI.Services;
using OverREALITY.UI.ViewModels;
using Xunit;

namespace OverREALITY.Tests.UI;

public class LoginViewModelTests
{
    private readonly Mock<IAuthService> _authServiceMock;
    private readonly Mock<INavigationService> _navigationServiceMock;

    public LoginViewModelTests()
    {
        _authServiceMock = new Mock<IAuthService>();
        _navigationServiceMock = new Mock<INavigationService>();
    }

    private LoginViewModel CreateViewModel()
    {
        return new LoginViewModel(_authServiceMock.Object, _navigationServiceMock.Object);
    }

    [Fact]
    public async Task LoginAsync_NormalAccount_NavigatesToDashboard()
    {
        var vm = CreateViewModel();
        vm.AccountKey = "ST-USER-1001:valid_token_1234567890abcdef";

        _authServiceMock.Setup(s => s.LoginAsync("ST-USER-1001", "valid_token_1234567890abcdef", null, It.IsAny<CancellationToken>()))
            .ReturnsAsync(Result<LoginResponse, AuthenticationError>.Success(new LoginResponse { AccessToken = "acc", RefreshToken = "ref" }));

        await vm.LoginCommand.ExecuteAsync(null);

        Assert.False(vm.Is2FaRequired);
        Assert.Empty(vm.ErrorMessage);
        Assert.False(vm.IsBusy);
        _navigationServiceMock.Verify(n => n.NavigateTo<DashboardViewModel>(), Times.Once);
    }

    [Fact]
    public async Task LoginAsync_When2FaRequired_TransitionsTo2FaScreenAndRetainsCredentials()
    {
        var vm = CreateViewModel();
        vm.AccountKey = "ST-USER-1001:valid_token_1234567890abcdef";

        _authServiceMock.Setup(s => s.LoginAsync("ST-USER-1001", "valid_token_1234567890abcdef", null, It.IsAny<CancellationToken>()))
            .ReturnsAsync(Result<LoginResponse, AuthenticationError>.Failure(new AuthenticationError
            {
                Message = "Two-factor authentication required",
                Code = "REQUIRES_2FA",
                StatusCode = 401,
                Requires2Fa = true
            }));

        await vm.LoginCommand.ExecuteAsync(null);

        Assert.True(vm.Is2FaRequired);
        Assert.Empty(vm.ErrorMessage);
        Assert.Empty(vm.TwoFaCode);
        Assert.False(vm.IsBusy);
        _navigationServiceMock.Verify(n => n.NavigateTo<DashboardViewModel>(), Times.Never);
    }

    [Fact]
    public async Task Verify2FaAsync_WithValidOtp_NavigatesToDashboardAndClearsChallengeState()
    {
        var vm = CreateViewModel();
        vm.AccountKey = "ST-USER-1001:valid_token_1234567890abcdef";

        _authServiceMock.Setup(s => s.LoginAsync("ST-USER-1001", "valid_token_1234567890abcdef", null, It.IsAny<CancellationToken>()))
            .ReturnsAsync(Result<LoginResponse, AuthenticationError>.Failure(new AuthenticationError
            {
                Requires2Fa = true,
                Code = "REQUIRES_2FA"
            }));

        await vm.LoginCommand.ExecuteAsync(null);
        Assert.True(vm.Is2FaRequired);

        // User enters OTP
        vm.TwoFaCode = "123456";

        _authServiceMock.Setup(s => s.LoginAsync("ST-USER-1001", "valid_token_1234567890abcdef", "123456", It.IsAny<CancellationToken>()))
            .ReturnsAsync(Result<LoginResponse, AuthenticationError>.Success(new LoginResponse { AccessToken = "acc_jwt", RefreshToken = "ref_jwt" }));

        await vm.Verify2FaCommand.ExecuteAsync(null);

        Assert.False(vm.Is2FaRequired);
        Assert.Empty(vm.TwoFaCode);
        Assert.Empty(vm.ErrorMessage);
        Assert.False(vm.IsBusy);
        _navigationServiceMock.Verify(n => n.NavigateTo<DashboardViewModel>(), Times.Once);
    }

    [Fact]
    public async Task Verify2FaAsync_WithBackupCode_NavigatesToDashboardAndClearsChallengeState()
    {
        var vm = CreateViewModel();
        vm.AccountKey = "ST-USER-1001:valid_token_1234567890abcdef";

        _authServiceMock.Setup(s => s.LoginAsync("ST-USER-1001", "valid_token_1234567890abcdef", null, It.IsAny<CancellationToken>()))
            .ReturnsAsync(Result<LoginResponse, AuthenticationError>.Failure(new AuthenticationError { Requires2Fa = true, Code = "REQUIRES_2FA" }));

        await vm.LoginCommand.ExecuteAsync(null);

        // User enters backup code
        vm.TwoFaCode = "backup-code-1234-5678";

        _authServiceMock.Setup(s => s.LoginAsync("ST-USER-1001", "valid_token_1234567890abcdef", "backup-code-1234-5678", It.IsAny<CancellationToken>()))
            .ReturnsAsync(Result<LoginResponse, AuthenticationError>.Success(new LoginResponse { AccessToken = "acc_backup", RefreshToken = "ref_backup" }));

        await vm.Verify2FaCommand.ExecuteAsync(null);

        Assert.False(vm.Is2FaRequired);
        Assert.Empty(vm.TwoFaCode);
        _navigationServiceMock.Verify(n => n.NavigateTo<DashboardViewModel>(), Times.Once);
    }

    [Fact]
    public async Task Verify2FaAsync_WithInvalidOtp_DisplaysErrorAndKeepsOtpScreenOpenForRetry()
    {
        var vm = CreateViewModel();
        vm.AccountKey = "ST-USER-1001:valid_token_1234567890abcdef";

        _authServiceMock.Setup(s => s.LoginAsync("ST-USER-1001", "valid_token_1234567890abcdef", null, It.IsAny<CancellationToken>()))
            .ReturnsAsync(Result<LoginResponse, AuthenticationError>.Failure(new AuthenticationError { Requires2Fa = true, Code = "REQUIRES_2FA" }));

        await vm.LoginCommand.ExecuteAsync(null);
        Assert.True(vm.Is2FaRequired);

        // Enter wrong OTP
        vm.TwoFaCode = "000000";

        _authServiceMock.Setup(s => s.LoginAsync("ST-USER-1001", "valid_token_1234567890abcdef", "000000", It.IsAny<CancellationToken>()))
            .ReturnsAsync(Result<LoginResponse, AuthenticationError>.Failure(new AuthenticationError
            {
                Message = "Authentication failed: invalid two-factor authentication code",
                Code = "Unauthorized",
                StatusCode = 401,
                Requires2Fa = false
            }));

        await vm.Verify2FaCommand.ExecuteAsync(null);

        // Screen remains open for another attempt
        Assert.True(vm.Is2FaRequired);
        Assert.Equal("Authentication failed: invalid two-factor authentication code", vm.ErrorMessage);
        _navigationServiceMock.Verify(n => n.NavigateTo<DashboardViewModel>(), Times.Never);
    }

    [Fact]
    public async Task Verify2FaAsync_WithEmptyOtp_DisplaysValidationMessageWithoutCallingApi()
    {
        var vm = CreateViewModel();
        vm.AccountKey = "ST-USER-1001:valid_token_1234567890abcdef";

        _authServiceMock.Setup(s => s.LoginAsync("ST-USER-1001", "valid_token_1234567890abcdef", null, It.IsAny<CancellationToken>()))
            .ReturnsAsync(Result<LoginResponse, AuthenticationError>.Failure(new AuthenticationError { Requires2Fa = true, Code = "REQUIRES_2FA" }));

        await vm.LoginCommand.ExecuteAsync(null);

        vm.TwoFaCode = "   "; // whitespace only

        await vm.Verify2FaCommand.ExecuteAsync(null);

        Assert.True(vm.Is2FaRequired);
        Assert.Equal("Please enter your 2FA code or backup code.", vm.ErrorMessage);
        _authServiceMock.Verify(s => s.LoginAsync(It.IsAny<string>(), It.IsAny<string>(), It.IsNotNull<string>(), It.IsAny<CancellationToken>()), Times.Never);
    }

    [Fact]
    public async Task Cancel2Fa_ClearsOtpAndChallengeCredentials_ReturnsToInitialScreen()
    {
        var vm = CreateViewModel();
        vm.AccountKey = "ST-USER-1001:valid_token_1234567890abcdef";

        _authServiceMock.Setup(s => s.LoginAsync("ST-USER-1001", "valid_token_1234567890abcdef", null, It.IsAny<CancellationToken>()))
            .ReturnsAsync(Result<LoginResponse, AuthenticationError>.Failure(new AuthenticationError { Requires2Fa = true, Code = "REQUIRES_2FA" }));

        await vm.LoginCommand.ExecuteAsync(null);
        Assert.True(vm.Is2FaRequired);

        vm.TwoFaCode = "123456";

        vm.Cancel2FaCommand.Execute(null);

        Assert.False(vm.Is2FaRequired);
        Assert.Empty(vm.TwoFaCode);
        Assert.Empty(vm.ErrorMessage);

        // Attempting to verify after cancel fails because challenge state is cleared
        await vm.Verify2FaCommand.ExecuteAsync(null);
        Assert.Equal("Please enter your 2FA code or backup code.", vm.ErrorMessage);
    }

    [Fact]
    public async Task LoginAsync_InvalidAccountKeyFormat_DisplaysFormatError()
    {
        var vm = CreateViewModel();
        vm.AccountKey = "invalid-no-colon";

        await vm.LoginCommand.ExecuteAsync(null);

        Assert.Equal("Invalid Account Key format. Expected format: AccountID:MasterToken", vm.ErrorMessage);
        _authServiceMock.Verify(s => s.LoginAsync(It.IsAny<string>(), It.IsAny<string>(), It.IsAny<string?>(), It.IsAny<CancellationToken>()), Times.Never);
    }

    [Fact]
    public async Task Commands_CannotExecute_WhileBusy()
    {
        var vm = CreateViewModel();
        vm.IsBusy = true;

        Assert.False(vm.LoginCommand.CanExecute(null));
        Assert.False(vm.Verify2FaCommand.CanExecute(null));
        Assert.False(vm.Cancel2FaCommand.CanExecute(null));

        vm.IsBusy = false;

        Assert.True(vm.LoginCommand.CanExecute(null));
        Assert.True(vm.Verify2FaCommand.CanExecute(null));
        Assert.True(vm.Cancel2FaCommand.CanExecute(null));
    }

    [Fact]
    public async Task Verify2FaAsync_WhenApiReturnsNetworkError_DisplaysError()
    {
        var vm = CreateViewModel();
        vm.AccountKey = "ST-USER-1001:valid_token_1234567890abcdef";

        _authServiceMock.Setup(s => s.LoginAsync("ST-USER-1001", "valid_token_1234567890abcdef", null, It.IsAny<CancellationToken>()))
            .ReturnsAsync(Result<LoginResponse, AuthenticationError>.Failure(new AuthenticationError { Requires2Fa = true, Code = "REQUIRES_2FA" }));

        await vm.LoginCommand.ExecuteAsync(null);

        vm.TwoFaCode = "123456";

        _authServiceMock.Setup(s => s.LoginAsync("ST-USER-1001", "valid_token_1234567890abcdef", "123456", It.IsAny<CancellationToken>()))
            .ReturnsAsync(Result<LoginResponse, AuthenticationError>.Failure(new AuthenticationError
            {
                Message = "Unable to connect to the server. Please check your network.",
                Code = "NETWORK_ERROR"
            }));

        await vm.Verify2FaCommand.ExecuteAsync(null);

        Assert.True(vm.Is2FaRequired);
        Assert.Equal("Unable to connect to the server. Please check your network.", vm.ErrorMessage);
    }
}
