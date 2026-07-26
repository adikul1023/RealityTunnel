using OverREALITY.Infrastructure.Services;
using OverREALITY.Shared.Models;
using Xunit;
using System.IO;

namespace OverREALITY.Tests.Infrastructure;

public class SettingsServiceTests
{
    [Fact]
    public void SaveAndLoadSettings_WorkCorrectly()
    {
        var settingsService = new SettingsService();
        var settings = new ClientSettings { AutoConnect = true, Theme = "Dark" };
        
        settingsService.SaveSettings(settings);
        
        var loadedSettings = settingsService.Settings;
        Assert.True(loadedSettings.AutoConnect);
        Assert.Equal("Dark", loadedSettings.Theme);
    }
}
