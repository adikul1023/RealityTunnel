using CommunityToolkit.Mvvm.ComponentModel;

namespace OverREALITY.UI.Services;

public interface INavigationService
{
    ObservableObject? CurrentView { get; }
    void NavigateTo<T>() where T : ObservableObject;
}
