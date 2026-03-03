using Microsoft.Win32;
using System;
using System.Runtime.InteropServices;

namespace RealityTunnel;

public class SystemProxyManager
{
    private const string InternetSettingsKey = @"Software\Microsoft\Windows\CurrentVersion\Internet Settings";

    [DllImport("wininet.dll")]
    private static extern bool InternetSetOption(IntPtr hInternet, int dwOption, IntPtr lpBuffer, int dwBufferLength);
    private const int INTERNET_OPTION_SETTINGS_CHANGED = 39;
    private const int INTERNET_OPTION_REFRESH = 37;

    public static void EnableProxy(string proxyAddress)
    {
        try
        {
            using RegistryKey? key = Registry.CurrentUser.OpenSubKey(InternetSettingsKey, true);
            if (key == null)
            {
                throw new InvalidOperationException("Cannot access Internet Settings registry key.");
            }

            key.SetValue("ProxyEnable", 1, RegistryValueKind.DWord);
            key.SetValue("ProxyServer", proxyAddress, RegistryValueKind.String);

            // Notify Windows that settings have changed
            InternetSetOption(IntPtr.Zero, INTERNET_OPTION_SETTINGS_CHANGED, IntPtr.Zero, 0);
            InternetSetOption(IntPtr.Zero, INTERNET_OPTION_REFRESH, IntPtr.Zero, 0);
        }
        catch (Exception ex)
        {
            throw new InvalidOperationException($"Failed to enable system proxy: {ex.Message}", ex);
        }
    }

    public static void DisableProxy()
    {
        try
        {
            using RegistryKey? key = Registry.CurrentUser.OpenSubKey(InternetSettingsKey, true);
            if (key == null)
            {
                throw new InvalidOperationException("Cannot access Internet Settings registry key.");
            }

            key.SetValue("ProxyEnable", 0, RegistryValueKind.DWord);
            key.DeleteValue("ProxyServer", false);

            // Notify Windows that settings have changed
            InternetSetOption(IntPtr.Zero, INTERNET_OPTION_SETTINGS_CHANGED, IntPtr.Zero, 0);
            InternetSetOption(IntPtr.Zero, INTERNET_OPTION_REFRESH, IntPtr.Zero, 0);
        }
        catch (Exception ex)
        {
            throw new InvalidOperationException($"Failed to disable system proxy: {ex.Message}", ex);
        }
    }

    public static bool IsProxyEnabled()
    {
        try
        {
            using RegistryKey? key = Registry.CurrentUser.OpenSubKey(InternetSettingsKey, false);
            if (key == null) return false;

            object? value = key.GetValue("ProxyEnable");
            return value != null && (int)value == 1;
        }
        catch
        {
            return false;
        }
    }
}
