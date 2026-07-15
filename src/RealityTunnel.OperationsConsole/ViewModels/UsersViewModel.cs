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
    public partial class UsersViewModel : ObservableObject
    {
        private readonly IAdminApiService _apiService;
        private readonly INavigationService _navigationService;
        private readonly IDialogService _dialogService;

        [ObservableProperty]
        private bool isBusy;

        [ObservableProperty]
        private ObservableCollection<UserAccountDisplayModel> accounts = new();

        [ObservableProperty]
        private string searchText = string.Empty;

        [ObservableProperty]
        private string selectedStatusFilter = "ALL";

        [ObservableProperty]
        private int currentPage = 1;

        [ObservableProperty]
        private int pageSize = 50;

        [ObservableProperty]
        private int totalCount;

        [ObservableProperty]
        private UserAccountDisplayModel? selectedAccount;

        public UsersViewModel(
            IAdminApiService apiService,
            INavigationService navigationService,
            IDialogService dialogService)
        {
            _apiService = apiService;
            _navigationService = navigationService;
            _dialogService = dialogService;
        }

        [RelayCommand]
        public async Task LoadAccountsAsync()
        {
            if (IsBusy) return;
            IsBusy = true;
            try
            {
                int offset = (CurrentPage - 1) * PageSize;
                string url = $"{ApiRoutes.Admin.Accounts}?limit={PageSize}&offset={offset}";

                var result = await _apiService.GetAsync<AdminAccountListResponse>(url);
                if (result.IsSuccess && result.Data != null)
                {
                    Accounts.Clear();
                    foreach (var acc in result.Data.Accounts)
                    {
                        // Filter locally if search text or status is set
                        if (!MatchesFilter(acc)) continue;

                        Accounts.Add(new UserAccountDisplayModel
                        {
                            Id = acc.Id,
                            AccountId = acc.AccountId,
                            Status = acc.Status,
                            PlanId = acc.PlanId,
                            SubscriptionExpiresAt = acc.SubscriptionExpiresAt,
                            CreatedAt = acc.CreatedAt
                        });
                    }
                    TotalCount = result.Data.Total;
                }
                else if (!result.IsUnauthorized && !result.IsForbidden)
                {
                    await _dialogService.ShowErrorAsync("Load Error", result.ErrorMessage ?? "Failed to load accounts list.");
                }
            }
            finally
            {
                IsBusy = false;
            }
        }

        private bool MatchesFilter(AdminAccountResponse acc)
        {
            if (!string.IsNullOrWhiteSpace(SearchText))
            {
                if (!acc.AccountId.Contains(SearchText.Trim(), StringComparison.OrdinalIgnoreCase) &&
                    !acc.Id.Contains(SearchText.Trim(), StringComparison.OrdinalIgnoreCase))
                {
                    return false;
                }
            }

            if (!string.IsNullOrEmpty(SelectedStatusFilter) && !SelectedStatusFilter.Equals("ALL", StringComparison.OrdinalIgnoreCase))
            {
                if (!acc.Status.Equals(SelectedStatusFilter, StringComparison.OrdinalIgnoreCase))
                {
                    return false;
                }
            }

            return true;
        }

        [RelayCommand]
        private async Task SearchAsync()
        {
            CurrentPage = 1;
            await LoadAccountsAsync();
        }

        [RelayCommand]
        private async Task NextPageAsync()
        {
            if (CurrentPage * PageSize < TotalCount)
            {
                CurrentPage++;
                await LoadAccountsAsync();
            }
        }

        [RelayCommand]
        private async Task PreviousPageAsync()
        {
            if (CurrentPage > 1)
            {
                CurrentPage--;
                await LoadAccountsAsync();
            }
        }

        [RelayCommand]
        private void InspectAccount(UserAccountDisplayModel? account)
        {
            if (account != null)
            {
                _navigationService.NavigateTo("UserDetails", account);
            }
        }
    }
}
