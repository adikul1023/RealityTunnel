using CommunityToolkit.Mvvm.ComponentModel;
using MaterialDesignThemes.Wpf;
using OverREALITY.Shared.Interfaces;
using OverREALITY.Shared.Models;
using System.Collections.Generic;

namespace OverREALITY.UI.ViewModels;

public partial class SettingsViewModel : ObservableObject
{
    private readonly ISettingsService _settingsService;

    [ObservableProperty]
    private bool _autoConnect;

    [ObservableProperty]
    private bool _startWithWindows;

    [ObservableProperty]
    private string _selectedTheme = "Light";

    [ObservableProperty]
    private string _selectedEnvironment = "Production";

    [ObservableProperty]
    private string _selectedLoggingLevel = "Information";

    public List<string> Themes { get; } = new() { "Light", "Dark" };
    public List<string> Environments { get; } = new() { "Production", "Staging", "Development" };
    public List<string> LoggingLevels { get; } = new() { "Trace", "Debug", "Information", "Warning", "Error", "Critical" };

    public SettingsViewModel(ISettingsService settingsService)
    {
        _settingsService = settingsService;
        var settings = _settingsService.Settings;
        AutoConnect = settings.AutoConnect;
        StartWithWindows = settings.StartWithWindows;
        SelectedTheme = settings.Theme;
        SelectedEnvironment = settings.Environment;
        SelectedLoggingLevel = settings.LoggingLevel;
        
        ApplyTheme(SelectedTheme);
    }

    private void SaveSettings()
    {
        _settingsService.SaveSettings(new ClientSettings
        {
            AutoConnect = AutoConnect,
            StartWithWindows = StartWithWindows,
            Theme = SelectedTheme,
            Environment = SelectedEnvironment,
            LoggingLevel = SelectedLoggingLevel
        });
    }

    partial void OnAutoConnectChanged(bool value) => SaveSettings();
    partial void OnStartWithWindowsChanged(bool value) => SaveSettings();
    partial void OnSelectedThemeChanged(string value)
    {
        ApplyTheme(value);
        SaveSettings();
    }
    partial void OnSelectedEnvironmentChanged(string value) => SaveSettings();
    partial void OnSelectedLoggingLevelChanged(string value) => SaveSettings();

    private void ApplyTheme(string themeName)
    {
        var paletteHelper = new PaletteHelper();
        var theme = paletteHelper.GetTheme();
        theme.SetBaseTheme(themeName == "Dark" ? Theme.Dark : Theme.Light);
        paletteHelper.SetTheme(theme);
    }
}
