using System;
using System.Collections.ObjectModel;
using System.Linq;
using System.Threading.Tasks;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using RealityTunnel.OperationsConsole.Services;
using RealityTunnel.OperationsConsole.Shared;

namespace RealityTunnel.OperationsConsole.ViewModels
{
    public partial class SubscriptionsViewModel : ObservableObject
    {
        private readonly IAdminApiService _apiService;
        private readonly IDialogService _dialogService;
        private readonly ISessionService _sessionService;

        [ObservableProperty]
        private bool isBusy;

        [ObservableProperty]
        private ObservableCollection<AdminSubscriptionDTO> subscriptions = new();

        [ObservableProperty]
        private ObservableCollection<AdminPlanDTO> availablePlans = new();

        [ObservableProperty]
        private string selectedStatusFilter = "ALL";

        [ObservableProperty]
        private int currentPage = 1;

        [ObservableProperty]
        private int pageSize = 50;

        [ObservableProperty]
        private int totalCount;

        [ObservableProperty]
        private AdminSubscriptionDTO? selectedSubscription;

        [ObservableProperty]
        private bool isSuperAdmin;

        public SubscriptionsViewModel(
            IAdminApiService apiService,
            IDialogService dialogService,
            ISessionService sessionService)
        {
            _apiService = apiService;
            _dialogService = dialogService;
            _sessionService = sessionService;
            IsSuperAdmin = _sessionService.CurrentRole.Equals("super_admin", StringComparison.OrdinalIgnoreCase);
        }

        [RelayCommand]
        public async Task LoadSubscriptionsAsync()
        {
            if (IsBusy) return;
            IsBusy = true;
            try
            {
                IsSuperAdmin = _sessionService.CurrentRole.Equals("super_admin", StringComparison.OrdinalIgnoreCase);

                if (AvailablePlans.Count == 0 && IsSuperAdmin)
                {
                    var planRes = await _apiService.GetAsync<System.Collections.Generic.List<AdminPlanDTO>>(ApiRoutes.Admin.Plans);
                    if (planRes.IsSuccess && planRes.Data != null)
                    {
                        AvailablePlans.Clear();
                        foreach (var p in planRes.Data) AvailablePlans.Add(p);
                    }
                }

                int offset = (CurrentPage - 1) * PageSize;
                string url = $"{ApiRoutes.Admin.Subscriptions}?limit={PageSize}&offset={offset}";
                if (!string.IsNullOrEmpty(SelectedStatusFilter) && !SelectedStatusFilter.Equals("ALL", StringComparison.OrdinalIgnoreCase))
                {
                    url += $"&status={SelectedStatusFilter.ToLowerInvariant()}";
                }

                var res = await _apiService.GetAsync<AdminSubscriptionListDTO>(url);
                if (res.IsSuccess && res.Data != null)
                {
                    Subscriptions.Clear();
                    foreach (var s in res.Data.Subscriptions)
                    {
                        s.SelectedPlanId = s.Plan;
                        s.IsPlanChanged = false;
                        Subscriptions.Add(s);
                    }
                    TotalCount = res.Data.Total;
                }
            }
            finally { IsBusy = false; }
        }

        [RelayCommand]
        private async Task ActivateAsync(AdminSubscriptionDTO? sub)
        {
            sub ??= SelectedSubscription;
            if (sub == null || !IsSuperAdmin) return;
            IsBusy = true;
            try
            {
                var res = await _apiService.PostAsync<AdminSubscriptionDTO>(ApiRoutes.Admin.ActivateSubscription(sub.Id));
                if (res.IsSuccess)
                {
                    await _dialogService.ShowInfoAsync("Activated", "Subscription forced to active state.");
                    await LoadSubscriptionsAsync();
                }
            }
            finally { IsBusy = false; }
        }

        [RelayCommand]
        private async Task GraceAsync(AdminSubscriptionDTO? sub)
        {
            sub ??= SelectedSubscription;
            if (sub == null || !IsSuperAdmin) return;
            IsBusy = true;
            try
            {
                var req = new AdminSubscriptionGraceRequest { GraceDurationDays = 7 };
                var res = await _apiService.PostAsync<AdminSubscriptionDTO, AdminSubscriptionGraceRequest>(
                    ApiRoutes.Admin.GraceSubscription(sub.Id), req);
                if (res.IsSuccess)
                {
                    await _dialogService.ShowInfoAsync("Grace Period Set", "Subscription placed in 7-day grace period.");
                    await LoadSubscriptionsAsync();
                }
            }
            finally { IsBusy = false; }
        }

        [RelayCommand]
        private async Task ExpireAsync(AdminSubscriptionDTO? sub)
        {
            sub ??= SelectedSubscription;
            if (sub == null || !IsSuperAdmin) return;
            IsBusy = true;
            try
            {
                var res = await _apiService.PostAsync<AdminSubscriptionDTO>(ApiRoutes.Admin.ExpireSubscription(sub.Id));
                if (res.IsSuccess)
                {
                    await _dialogService.ShowInfoAsync("Expired", "Subscription marked as expired.");
                    await LoadSubscriptionsAsync();
                }
            }
            finally { IsBusy = false; }
        }

        [RelayCommand]
        private async Task CancelAsync(AdminSubscriptionDTO? sub)
        {
            sub ??= SelectedSubscription;
            if (sub == null || !IsSuperAdmin) return;
            bool confirm = await _dialogService.ShowConfirmationAsync("Confirm Cancellation", $"Are you sure you want to cancel subscription {sub.Id}?");
            if (!confirm) return;

            IsBusy = true;
            try
            {
                var res = await _apiService.PostAsync<AdminSubscriptionDTO>(ApiRoutes.Admin.CancelSubscription(sub.Id));
                if (res.IsSuccess)
                {
                    await _dialogService.ShowInfoAsync("Cancelled", "Subscription has been cancelled.");
                    await LoadSubscriptionsAsync();
                }
            }
            finally { IsBusy = false; }
        }

        [RelayCommand]
        private async Task RenewAsync(AdminSubscriptionDTO? sub)
        {
            sub ??= SelectedSubscription;
            if (sub == null || !IsSuperAdmin) return;
            IsBusy = true;
            try
            {
                var req = new AdminSubscriptionRenewRequest { NewExpiresAt = DateTime.UtcNow.AddDays(30) };
                var res = await _apiService.PostAsync<AdminSubscriptionDTO, AdminSubscriptionRenewRequest>(
                    ApiRoutes.Admin.RenewSubscription(sub.Id), req);
                if (res.IsSuccess)
                {
                    await _dialogService.ShowInfoAsync("Renewed", "Subscription renewed/extended by 30 days.");
                    await LoadSubscriptionsAsync();
                }
            }
            finally { IsBusy = false; }
        }

        [RelayCommand]
        private async Task RevokeAsync(AdminSubscriptionDTO? sub)
        {
            sub ??= SelectedSubscription;
            if (sub == null || !IsSuperAdmin) return;
            bool confirm = await _dialogService.ShowConfirmationAsync("Confirm Revocation", $"Are you sure you want to forcibly revoke subscription {sub.Id}?");
            if (!confirm) return;

            IsBusy = true;
            try
            {
                var req = new AdminSubscriptionRevokeRequest { Reason = "Administrative Revocation from UI" };
                var res = await _apiService.PostAsync<AdminSubscriptionDTO, AdminSubscriptionRevokeRequest>(
                    ApiRoutes.Admin.RevokeSubscription(sub.Id), req);
                if (res.IsSuccess)
                {
                    await _dialogService.ShowInfoAsync("Revoked", "Subscription has been revoked.");
                    await LoadSubscriptionsAsync();
                }
                else
                {
                    await _dialogService.ShowErrorAsync("Revocation Failed", res.ErrorMessage ?? "Failed to revoke subscription.");
                }
            }
            finally { IsBusy = false; }
        }

        [RelayCommand]
        private async Task EditPlanAsync(AdminSubscriptionDTO? sub)
        {
            sub ??= SelectedSubscription;
            if (sub == null || !IsSuperAdmin || string.IsNullOrEmpty(sub.SelectedPlanId) || !sub.IsPlanChanged) return;
            
            string newPlan = sub.SelectedPlanId;
            bool confirm = await _dialogService.ShowConfirmationAsync("Confirm Edit Plan", $"Are you sure you want to change subscription {sub.Id} from {sub.Plan} to {newPlan}?");
            if (!confirm) return;

            IsBusy = true;
            try
            {
                var req = new AdminSubscriptionPlanRequest { PlanId = newPlan };
                var res = await _apiService.PutAsync<AdminSubscriptionDTO, AdminSubscriptionPlanRequest>(
                    ApiRoutes.Admin.EditSubscriptionPlan(sub.Id), req);
                
                if (res.IsSuccess)
                {
                    await _dialogService.ShowInfoAsync("Plan Edited", $"Subscription plan changed to {newPlan}.");
                    await LoadSubscriptionsAsync();
                }
                else
                {
                    await _dialogService.ShowErrorAsync("Edit Plan Failed", res.ErrorMessage ?? "Failed to edit subscription plan.");
                }
            }
            finally { IsBusy = false; }
        }
    }
}
