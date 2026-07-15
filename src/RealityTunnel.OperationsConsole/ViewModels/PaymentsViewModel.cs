using System;
using System.Collections.ObjectModel;
using System.Threading.Tasks;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using RealityTunnel.OperationsConsole.Services;
using RealityTunnel.OperationsConsole.Shared;

namespace RealityTunnel.OperationsConsole.ViewModels
{
    public partial class PaymentsViewModel : ObservableObject
    {
        private readonly IAdminApiService _apiService;
        private readonly IDialogService _dialogService;
        private readonly ISessionService _sessionService;

        [ObservableProperty]
        private bool isBusy;

        [ObservableProperty]
        private ObservableCollection<AdminPaymentDTO> payments = new();

        [ObservableProperty]
        private string selectedStatusFilter = "ALL";

        [ObservableProperty]
        private int currentPage = 1;

        [ObservableProperty]
        private int pageSize = 50;

        [ObservableProperty]
        private int totalCount;

        [ObservableProperty]
        private AdminPaymentDTO? selectedPayment;

        [ObservableProperty]
        private bool isSuperAdmin;

        [ObservableProperty]
        private string resolveReasonInput = "Manual resolution by operator";

        public PaymentsViewModel(
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
        public async Task LoadPaymentsAsync()
        {
            if (IsBusy) return;
            IsBusy = true;
            try
            {
                IsSuperAdmin = _sessionService.CurrentRole.Equals("super_admin", StringComparison.OrdinalIgnoreCase);
                int offset = (CurrentPage - 1) * PageSize;
                string url = $"{ApiRoutes.Admin.Payments}?limit={PageSize}&offset={offset}";
                if (!string.IsNullOrEmpty(SelectedStatusFilter) && !SelectedStatusFilter.Equals("ALL", StringComparison.OrdinalIgnoreCase))
                {
                    url += $"&status={SelectedStatusFilter.ToLowerInvariant()}";
                }

                var res = await _apiService.GetAsync<AdminPaymentListDTO>(url);
                if (res.IsSuccess && res.Data != null)
                {
                    Payments.Clear();
                    foreach (var p in res.Data.Payments) Payments.Add(p);
                    TotalCount = res.Data.Total;
                }
            }
            finally { IsBusy = false; }
        }

        [RelayCommand]
        private async Task ReconcileAsync(AdminPaymentDTO? payment)
        {
            payment ??= SelectedPayment;
            if (payment == null || !IsSuperAdmin) return;
            IsBusy = true;
            try
            {
                var res = await _apiService.PostAsync<AdminPaymentDTO>(ApiRoutes.Admin.ReconcilePayment(payment.Id));
                if (res.IsSuccess)
                {
                    await _dialogService.ShowInfoAsync("Reconciled", $"Payment {payment.Id} successfully reconciled with payment gateway.");
                    await LoadPaymentsAsync();
                }
            }
            finally { IsBusy = false; }
        }

        [RelayCommand]
        private async Task ResolveAsync(AdminPaymentDTO? payment)
        {
            payment ??= SelectedPayment;
            if (payment == null || !IsSuperAdmin) return;
            bool confirm = await _dialogService.ShowConfirmationAsync("Confirm Manual Resolve", $"Are you sure you want to manually resolve payment {payment.Id}?");
            if (!confirm) return;

            IsBusy = true;
            try
            {
                var req = new AdminPaymentResolveRequest { Reason = ResolveReasonInput };
                var res = await _apiService.PostAsync<AdminPaymentDTO, AdminPaymentResolveRequest>(
                    ApiRoutes.Admin.ResolvePayment(payment.Id), req);
                if (res.IsSuccess)
                {
                    await _dialogService.ShowInfoAsync("Resolved", $"Payment {payment.Id} marked as resolved.");
                    await LoadPaymentsAsync();
                }
            }
            finally { IsBusy = false; }
        }
    }
}
