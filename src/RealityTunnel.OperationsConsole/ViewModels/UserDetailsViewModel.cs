using System;
using System.Collections.ObjectModel;
using System.Linq;
using System.Threading.Tasks;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using RealityTunnel.OperationsConsole.Models;
using RealityTunnel.OperationsConsole.Services;
using RealityTunnel.OperationsConsole.Shared;

namespace RealityTunnel.OperationsConsole.ViewModels
{
    public partial class UserDetailsViewModel : ObservableObject
    {
        private readonly IAdminApiService _apiService;
        private readonly INavigationService _navigationService;
        private readonly IDialogService _dialogService;
        private readonly ISessionService _sessionService;

        [ObservableProperty]
        private bool isBusy;

        [ObservableProperty]
        private UserAccountDisplayModel? account;

        [ObservableProperty]
        private ObservableCollection<AdminDeviceResponse> devices = new();

        [ObservableProperty]
        private ObservableCollection<AdminSignalResponse> signals = new();

        [ObservableProperty]
        private AdminProvisioningDTO? provisioningProfile;

        [ObservableProperty]
        private AdminSubscriptionDTO? subscriptionDetails;

        [ObservableProperty]
        private bool isSuperAdmin;

        [ObservableProperty]
        private bool isOracleHealthy = false;

        [ObservableProperty]
        private bool isMarzbanHealthy = false;

        [ObservableProperty]
        private bool isClientConfigHealthy = false;

        [ObservableProperty]
        private bool canRemoveSingleDevice = true;

        [ObservableProperty]
        private string removeDeviceTooltip = "Remove this device and instantly revoke its VPN access.";

        [ObservableProperty]
        private int extendDaysInput = 30;

        [ObservableProperty]
        private string grantPlanId = "standard";

        [ObservableProperty]
        private int grantDurationDays = 30;

        [ObservableProperty]
        private string grantPaymentReference = "";

        public UserDetailsViewModel(
            IAdminApiService apiService,
            INavigationService navigationService,
            IDialogService dialogService,
            ISessionService sessionService)
        {
            _apiService = apiService;
            _navigationService = navigationService;
            _dialogService = dialogService;
            _sessionService = sessionService;
            IsSuperAdmin = _sessionService.CurrentRole.Equals("super_admin", StringComparison.OrdinalIgnoreCase);
        }

        public async Task LoadDetailsAsync(UserAccountDisplayModel initialAccount)
        {
            Account = initialAccount;
            IsBusy = true;
            try
            {
                IsSuperAdmin = _sessionService.CurrentRole.Equals("super_admin", StringComparison.OrdinalIgnoreCase);

                // 1. Fetch exact account
                var accRes = await _apiService.GetAsync<AdminAccountResponse>(ApiRoutes.Admin.GetAccount(initialAccount.AccountId));
                if (accRes.IsSuccess && accRes.Data != null)
                {
                    Account.Status = accRes.Data.Status;
                    Account.PlanId = accRes.Data.PlanId;
                    Account.SubscriptionExpiresAt = accRes.Data.SubscriptionExpiresAt;
                    IsOracleHealthy = true;
                }
                else
                {
                    IsOracleHealthy = false;
                    await _dialogService.ShowErrorAsync("Load Error", accRes.ErrorMessage ?? "Failed to fetch exact account details.");
                }

                // 2. Fetch registered devices
                var devRes = await _apiService.GetAsync<AdminDeviceListResponse>(ApiRoutes.Admin.GetDevices(initialAccount.AccountId));
                if (devRes.IsSuccess && devRes.Data != null)
                {
                    Devices.Clear();
                    foreach (var d in devRes.Data.Devices) Devices.Add(d);
                    Account.DeviceCount = Devices.Count;
                }

                // 3. Fetch security signals
                var sigRes = await _apiService.GetAsync<AdminSignalListResponse>(ApiRoutes.Admin.GetSignals(initialAccount.AccountId));
                if (sigRes.IsSuccess && sigRes.Data != null)
                {
                    Signals.Clear();
                    foreach (var s in sigRes.Data.Signals.OrderByDescending(x => x.OccurredAt)) Signals.Add(s);
                }

                // 4. Fetch VPN Provisioning profile
                var provRes = await _apiService.GetAsync<AdminProvisioningListDTO>(ApiRoutes.Admin.Provisioning);
                if (provRes.IsSuccess && provRes.Data != null)
                {
                    ProvisioningProfile = provRes.Data.Profiles.FirstOrDefault(p =>
                        p.AccountId.Equals(initialAccount.AccountId, StringComparison.OrdinalIgnoreCase) ||
                        p.AccountId.Equals(initialAccount.Id, StringComparison.OrdinalIgnoreCase));
                    Account.Provisioning = ProvisioningProfile;

                    IsMarzbanHealthy = ProvisioningProfile != null && (
                        ProvisioningProfile.ProvisionStatus.Equals("synced", StringComparison.OrdinalIgnoreCase) ||
                        ProvisioningProfile.ProvisionStatus.Equals("active", StringComparison.OrdinalIgnoreCase));

                    IsClientConfigHealthy = ProvisioningProfile != null && !string.IsNullOrEmpty(ProvisioningProfile.VpnProfileUuid);
                }
                else
                {
                    IsMarzbanHealthy = false;
                    IsClientConfigHealthy = false;
                }

                // 5. Fetch Subscriptions to find exact data usage
                var subRes = await _apiService.GetAsync<AdminSubscriptionListDTO>(ApiRoutes.Admin.Subscriptions);
                if (subRes.IsSuccess && subRes.Data != null)
                {
                    SubscriptionDetails = subRes.Data.Subscriptions.FirstOrDefault(s =>
                        s.AccountId.Equals(initialAccount.AccountId, StringComparison.OrdinalIgnoreCase) ||
                        s.AccountId.Equals(initialAccount.Id, StringComparison.OrdinalIgnoreCase));

                    if (SubscriptionDetails != null)
                    {
                        Account.Subscription = SubscriptionDetails;
                        Account.DataUsedBytes = SubscriptionDetails.DataUsedBytes;
                        Account.DataLimitBytes = SubscriptionDetails.DataLimitBytes > 0 ? SubscriptionDetails.DataLimitBytes : 53687091200;
                    }
                }
            }
            finally
            {
                IsBusy = false;
            }
        }

        [RelayCommand]
        private void BackToUsers()
        {
            _navigationService.NavigateTo("Users");
        }

        [RelayCommand]
        private async Task SuspendAccountAsync()
        {
            if (Account == null || !IsSuperAdmin) return;
            bool confirm = await _dialogService.ShowConfirmationAsync("Confirm Suspend", $"Are you sure you want to suspend account {Account.AccountId}?");
            if (!confirm) return;

            IsBusy = true;
            try
            {
                var res = await _apiService.PatchAsync<AdminAccountResponse>(ApiRoutes.Admin.SuspendAccount(Account.AccountId));
                if (res.IsSuccess && res.Data != null)
                {
                    Account.Status = res.Data.Status;
                    await _dialogService.ShowInfoAsync("Success", "Account has been suspended.");
                }
            }
            finally { IsBusy = false; }
        }

        [RelayCommand]
        private async Task ActivateAccountAsync()
        {
            if (Account == null || !IsSuperAdmin) return;
            IsBusy = true;
            try
            {
                var res = await _apiService.PatchAsync<AdminAccountResponse>(ApiRoutes.Admin.ActivateAccount(Account.AccountId));
                if (res.IsSuccess && res.Data != null)
                {
                    Account.Status = res.Data.Status;
                    await _dialogService.ShowInfoAsync("Success", "Account activated successfully.");
                }
            }
            finally { IsBusy = false; }
        }

        [RelayCommand]
        private async Task ExtendSubscriptionAsync()
        {
            if (Account == null || !IsSuperAdmin) return;
            IsBusy = true;
            try
            {
                var req = new ExtendSubscriptionRequest { Days = ExtendDaysInput };
                var res = await _apiService.PatchAsync<AdminAccountResponse, ExtendSubscriptionRequest>(
                    ApiRoutes.Admin.ExtendSubscription(Account.AccountId), req);

                if (res.IsSuccess && res.Data != null)
                {
                    Account.SubscriptionExpiresAt = res.Data.SubscriptionExpiresAt;
                    await _dialogService.ShowInfoAsync("Success", $"Subscription extended by {ExtendDaysInput} days.");
                }
            }
            finally { IsBusy = false; }
        }

        [RelayCommand]
        private async Task GrantSubscriptionAsync()
        {
            if (Account == null || !IsSuperAdmin) return;
            
            string refStr = string.IsNullOrWhiteSpace(GrantPaymentReference) ? "None" : GrantPaymentReference;
            string confirmationMessage = $"Grant Benefits\n\nAccount:\n{Account.AccountId}\n\nPlan:\n{GrantPlanId}\n\nDuration:\n{GrantDurationDays} days\n\nPayment Reference:\n{refStr}\n\nProceed?";
            
            bool confirm = await _dialogService.ShowConfirmationAsync("Confirm Grant", confirmationMessage);
            if (!confirm) return;

            IsBusy = true;
            try
            {
                var req = new AdminGrantSubscriptionRequest
                {
                    PlanId = GrantPlanId,
                    DurationDays = GrantDurationDays,
                    PaymentMethod = "manual_qr",
                    PaymentReference = string.IsNullOrWhiteSpace(GrantPaymentReference) ? null : GrantPaymentReference,
                    Notes = "Beta manual onboarding"
                };

                var res = await _apiService.PostAsync<AdminGrantSubscriptionResponse, AdminGrantSubscriptionRequest>(
                    ApiRoutes.Admin.GrantSubscription(Account.AccountId), req);

                if (res.IsSuccess && res.Data != null)
                {
                    Account.PlanId = res.Data.Plan;
                    Account.SubscriptionExpiresAt = res.Data.ExpiresAt;
                    
                    if (res.Data.SyncStatus == "success" || res.Data.ProvisioningState == "ACTIVE")
                    {
                        await _dialogService.ShowInfoAsync("Success", "🟢 Subscription granted successfully\n🟢 VPN synchronized");
                    }
                    else
                    {
                        await _dialogService.ShowInfoAsync("Partial Success", "🟢 Subscription granted\n🟡 VPN synchronization queued (will retry automatically)");
                    }
                    
                    // Reload to get updated Provisioning and Subscription data
                    await LoadDetailsAsync(Account);
                }
            }
            finally { IsBusy = false; }
        }

        [RelayCommand]
        private async Task ForceLogoutAllSessionsAsync()
        {
            if (Account == null || !IsSuperAdmin) return;
            bool confirm = await _dialogService.ShowConfirmationAsync("Confirm Force Logout",
                $"Are you sure you want to revoke all active sessions for {Account.AccountId}?");
            if (!confirm) return;

            IsBusy = true;
            try
            {
                var res = await _apiService.PostAsync<AdminLogoutAllResponse>(ApiRoutes.Admin.LogoutAllSessions(Account.AccountId));
                if (res.IsSuccess && res.Data != null)
                {
                    await _dialogService.ShowInfoAsync("Sessions Revoked", $"Successfully revoked {res.Data.RevokedCount} active session(s).");
                }
            }
            finally { IsBusy = false; }
        }

        [RelayCommand]
        private async Task SyncVpnAsync()
        {
            if (ProvisioningProfile == null || !IsSuperAdmin) return;
            IsBusy = true;
            try
            {
                var res = await _apiService.PostAsync<AdminProvisioningDTO>(ApiRoutes.Admin.SyncProvisioning(ProvisioningProfile.Id));
                if (res.IsSuccess && res.Data != null)
                {
                    ProvisioningProfile = res.Data;
                    await _dialogService.ShowInfoAsync("VPN Synced", "Successfully synchronized VPN profile with remote Marzban server.");
                }
            }
            finally { IsBusy = false; }
        }

        [RelayCommand]
        private async Task RetryVpnAsync()
        {
            if (ProvisioningProfile == null || !IsSuperAdmin) return;
            IsBusy = true;
            try
            {
                var res = await _apiService.PostAsync<AdminProvisioningDTO>(ApiRoutes.Admin.RetryProvisioning(ProvisioningProfile.Id));
                if (res.IsSuccess && res.Data != null)
                {
                    ProvisioningProfile = res.Data;
                    await _dialogService.ShowInfoAsync("VPN Retry", "Provisioning retry executed successfully.");
                }
            }
            finally { IsBusy = false; }
        }

        [RelayCommand]
        private async Task SuspendVpnAsync()
        {
            if (ProvisioningProfile == null || !IsSuperAdmin) return;
            IsBusy = true;
            try
            {
                var res = await _apiService.PostAsync<AdminProvisioningDTO>(ApiRoutes.Admin.SuspendProvisioning(ProvisioningProfile.Id));
                if (res.IsSuccess && res.Data != null)
                {
                    ProvisioningProfile = res.Data;
                    await _dialogService.ShowInfoAsync("VPN Suspended", "Profile suspended on remote VPN gateway.");
                }
            }
            finally { IsBusy = false; }
        }

        [RelayCommand]
        private async Task RestoreVpnAsync()
        {
            if (ProvisioningProfile == null || !IsSuperAdmin) return;
            IsBusy = true;
            try
            {
                var res = await _apiService.PostAsync<AdminProvisioningDTO>(ApiRoutes.Admin.RestoreProvisioning(ProvisioningProfile.Id));
                if (res.IsSuccess && res.Data != null)
                {
                    ProvisioningProfile = res.Data;
                    await _dialogService.ShowInfoAsync("VPN Restored", "Profile restored on remote VPN gateway.");
                }
            }
            finally { IsBusy = false; }
        }

        [RelayCommand]
        private async Task TerminateVpnAsync()
        {
            if (ProvisioningProfile == null || !IsSuperAdmin) return;
            bool confirm = await _dialogService.ShowConfirmationAsync("Confirm VPN Termination",
                "Are you sure you want to permanently terminate and delete this VPN profile on Marzban?");
            if (!confirm) return;

            IsBusy = true;
            try
            {
                var res = await _apiService.PostAsync<AdminProvisioningDTO>(ApiRoutes.Admin.TerminateProvisioning(ProvisioningProfile.Id));
                if (res.IsSuccess)
                {
                    ProvisioningProfile = res.Data;
                    await _dialogService.ShowInfoAsync("VPN Terminated", "Profile terminated on remote VPN gateway.");
                }
            }
            finally { IsBusy = false; }
        }

        [RelayCommand]
        private async Task RemoveSingleDeviceAsync(AdminDeviceResponse? device)
        {
            if (device == null || Account == null || !IsSuperAdmin) return;

            bool confirm = await _dialogService.ShowConfirmationAsync("Confirm Remove Device",
                $"Are you sure you want to forcefully remove and revoke the device '{device.FriendlyName}' (GUID: {device.DeviceGuid})?\n\nThis will instantly terminate its VPN access.");
            if (!confirm) return;

            IsBusy = true;
            try
            {
                var res = await _apiService.DeleteAsync<DeviceRemovalResponseDTO>(ApiRoutes.Admin.RemoveDevice(Account.AccountId, device.DeviceGuid));
                if (res.IsSuccess)
                {
                    await _dialogService.ShowInfoAsync("Device Removed", "The device was successfully removed and its sessions revoked.");
                    Devices.Remove(device);
                }
                else
                {
                    await _dialogService.ShowErrorAsync("Removal Failed", res.ErrorMessage ?? "Failed to remove the device.");
                }
            }
            finally { IsBusy = false; }
        }

        [RelayCommand]
        private async Task DeleteAccountAsync()
        {
            if (Account == null || !IsSuperAdmin) return;
            
            bool confirm = await _dialogService.ShowConfirmationAsync("Confirm Delete User",
                $"Are you absolutely sure you want to logically delete the user {Account.AccountId}?\n\nThis will revoke all active VPN sessions, terminate provisioning on the gateway, and hide the user. Billing and audit history will be retained.");
            if (!confirm) return;

            IsBusy = true;
            try
            {
                var res = await _apiService.DeleteAsync<AdminAccountResponse>(ApiRoutes.Admin.DeleteAccount(Account.AccountId));
                if (res.IsSuccess)
                {
                    await _dialogService.ShowInfoAsync("User Deleted", "The user account has been successfully deleted.");
                    _navigationService.NavigateTo("Users");
                }
                else
                {
                    await _dialogService.ShowErrorAsync("Delete Failed", res.ErrorMessage ?? "Failed to delete user.");
                }
            }
            finally { IsBusy = false; }
        }
    }
}
