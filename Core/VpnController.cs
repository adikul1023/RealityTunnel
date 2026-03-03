using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Net.NetworkInformation;
using System.Net.Sockets;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Threading;

namespace OverREALITY.Core;

/// <summary>
/// Manages the sing-box process and all TUN routing — cross-platform.
/// Windows uses netsh/route; Linux uses ip commands.
/// </summary>
public class VpnController
{
    private Process? _process;
    private string?  _serverIp;
    private string?  _realGateway;

    private const string TunGateway  = "10.0.85.1";
    private const string TunAddress  = "10.0.85.2";
    private const string TunPrefix   = "24";
    private const string AdapterName = "singbox_tun";

    private static bool IsLinux => RuntimeInformation.IsOSPlatform(OSPlatform.Linux);

    public void Start(string serverIp)
    {
        if (IsRunning())
            throw new InvalidOperationException("Already running.");

        string appDir       = GetAppDirectory();
        string coreExe      = IsLinux ? "sing-box" : "sing-box.exe";
        string corePath     = Path.Combine(appDir, coreExe);
        string templatePath = Path.Combine(appDir, "config.template.json");
        string configPath   = Path.Combine(appDir, "config.json");
        string logPath      = Path.Combine(appDir, "singbox.log");

        if (!File.Exists(corePath))
            throw new FileNotFoundException(
                $"{coreExe} not found in app directory.\n" +
                "Download: https://github.com/SagerNet/sing-box/releases");
        if (!File.Exists(templatePath))
            throw new FileNotFoundException("config.template.json not found.");

        _realGateway = GetDefaultGateway()
            ?? throw new InvalidOperationException("Cannot determine default gateway.");
        _serverIp = serverIp;

        var envVars = LoadDotEnv(appDir);
        string config = File.ReadAllText(templatePath).Replace("{{SERVER_IP}}", serverIp);
        foreach (var kv in envVars)
            config = config.Replace($"{{{{{kv.Key}}}}}", kv.Value);
        File.WriteAllText(configPath, config);

        foreach (var orphan in Process.GetProcessesByName("sing-box"))
        {
            try { orphan.Kill(entireProcessTree: true); orphan.WaitForExit(3000); } catch { }
            orphan.Dispose();
        }

        _process = Process.Start(new ProcessStartInfo
        {
            FileName         = corePath,
            Arguments        = "run -c config.json",
            WorkingDirectory = appDir,
            UseShellExecute  = false,
            CreateNoWindow   = true,
            RedirectStandardOutput = true,
            RedirectStandardError  = true
        }) ?? throw new InvalidOperationException("Failed to launch sing-box.");

        Thread.Sleep(4000);

        if (_process.HasExited)
        {
            _process.Dispose();
            _process = null;
            string log = File.Exists(logPath) ? File.ReadAllText(logPath).Trim() : "(no log)";
            throw new InvalidOperationException($"sing-box exited immediately.\n\nLog:\n{log}");
        }

        try
        {
            if (IsLinux)
                SetupRoutesLinux(serverIp);
            else
                SetupRoutesWindows(serverIp);
        }
        catch
        {
            Stop();
            throw;
        }
    }

    public void Stop()
    {
        try
        {
            if (IsLinux)
                TeardownRoutesLinux();
            else
                TeardownRoutesWindows();
        }
        catch { }

        if (_process != null)
        {
            try
            {
                if (!_process.HasExited)
                {
                    _process.Kill(entireProcessTree: true);
                    _process.WaitForExit(5000);
                }
            }
            catch { }
            finally
            {
                _process.Dispose();
                _process = null;
            }
        }
        _serverIp    = null;
        _realGateway = null;
    }

    public bool IsRunning() => _process != null && !_process.HasExited;

    // ── Windows routing ────────────────────────────────────────────────────
    private void SetupRoutesWindows(string serverIp)
    {
        RunCmd("netsh", $"interface ip set address \"{AdapterName}\" static {TunAddress} 255.255.255.0");
        RunCmd("netsh", $"interface ip set dns name=\"{AdapterName}\" static 8.8.8.8 validate=no");
        RunCmd("netsh", $"interface ip add dns name=\"{AdapterName}\" 8.8.4.4 index=2 validate=no");
        RunCmd("route", $"add {serverIp} mask 255.255.255.255 {_realGateway} metric 5");
        RunCmd("route", $"add 0.0.0.0 mask 128.0.0.0 {TunGateway} metric 6");
        RunCmd("route", $"add 128.0.0.0 mask 128.0.0.0 {TunGateway} metric 6");
    }

    private void TeardownRoutesWindows()
    {
        if (!string.IsNullOrEmpty(_serverIp))
            try { RunCmd("route", $"delete {_serverIp} mask 255.255.255.255"); } catch { }
        try { RunCmd("route", $"delete 0.0.0.0 mask 128.0.0.0 {TunGateway}"); } catch { }
        try { RunCmd("route", $"delete 128.0.0.0 mask 128.0.0.0 {TunGateway}"); } catch { }
    }

    // ── Linux routing ──────────────────────────────────────────────────────
    private void SetupRoutesLinux(string serverIp)
    {
        RunCmd("ip", $"addr add {TunAddress}/{TunPrefix} dev {AdapterName}");
        RunCmd("ip", $"link set {AdapterName} up");
        RunCmd("ip", $"route add {serverIp}/32 via {_realGateway}");
        RunCmd("ip", $"route add 0.0.0.0/1 via {TunGateway} dev {AdapterName}");
        RunCmd("ip", $"route add 128.0.0.0/1 via {TunGateway} dev {AdapterName}");
        // DNS via resolvconf/systemd-resolved
        RunCmd("bash", $"-c \"echo 'nameserver 8.8.8.8' | resolvconf -a {AdapterName} 2>/dev/null || true\"");
    }

    private void TeardownRoutesLinux()
    {
        if (!string.IsNullOrEmpty(_serverIp))
            try { RunCmd("ip", $"route del {_serverIp}/32"); } catch { }
        try { RunCmd("ip", $"route del 0.0.0.0/1 via {TunGateway}"); } catch { }
        try { RunCmd("ip", $"route del 128.0.0.0/1 via {TunGateway}"); } catch { }
        try { RunCmd("ip", $"link set {AdapterName} down"); } catch { }
        try { RunCmd("ip", $"addr del {TunAddress}/{TunPrefix} dev {AdapterName}"); } catch { }
        try { RunCmd("bash", $"-c \"resolvconf -d {AdapterName} 2>/dev/null || true\""); } catch { }
    }

    // ── Helpers ────────────────────────────────────────────────────────────
    public static string GetAppDirectory()
    {
        string? path = Environment.ProcessPath;
        if (string.IsNullOrEmpty(path))
            path = Assembly.GetExecutingAssembly().Location;
        return Path.GetDirectoryName(path) ?? AppContext.BaseDirectory;
    }

    private static void RunCmd(string cmd, string args)
    {
        using var p = Process.Start(new ProcessStartInfo
        {
            FileName = cmd, Arguments = args,
            UseShellExecute = false, CreateNoWindow = true,
            RedirectStandardOutput = true, RedirectStandardError = true
        });
        p?.WaitForExit(10000);
    }

    public static Dictionary<string, string> LoadDotEnv(string appDir)
    {
        var result = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        string path = Path.Combine(appDir, ".env");
        if (!File.Exists(path)) return result;
        foreach (string line in File.ReadLines(path))
        {
            string trimmed = line.Trim();
            if (trimmed.StartsWith('#') || trimmed.Length == 0) continue;
            int eq = trimmed.IndexOf('=');
            if (eq < 1) continue;
            string key = trimmed[..eq].Trim();
            string val = trimmed[(eq + 1)..].Trim();
            if (!string.IsNullOrEmpty(key))
                result[key] = val;
        }
        return result;
    }

    private static string? GetDefaultGateway()
    {
        if (IsLinux)
        {
            // Parse `ip route show default`
            try
            {
                using var p = Process.Start(new ProcessStartInfo
                {
                    FileName = "ip", Arguments = "route show default",
                    UseShellExecute = false, RedirectStandardOutput = true
                });
                string output = p?.StandardOutput.ReadToEnd() ?? "";
                p?.WaitForExit(5000);
                // "default via 192.168.1.1 dev eth0"
                var parts = output.Split(' ', StringSplitOptions.RemoveEmptyEntries);
                int idx = Array.IndexOf(parts, "via");
                if (idx >= 0 && idx + 1 < parts.Length)
                    return parts[idx + 1];
            }
            catch { }
            return null;
        }

        return NetworkInterface.GetAllNetworkInterfaces()
            .Where(ni => ni.OperationalStatus == OperationalStatus.Up
                      && ni.NetworkInterfaceType != NetworkInterfaceType.Loopback)
            .Select(ni => new {
                gw    = ni.GetIPProperties().GatewayAddresses
                           .FirstOrDefault(g => g.Address.AddressFamily == AddressFamily.InterNetwork
                                             && g.Address.ToString() != "0.0.0.0"),
                index = ni.GetIPProperties().GetIPv4Properties()?.Index ?? 9999
            })
            .Where(x => x.gw != null)
            .OrderBy(x => x.index)
            .Select(x => x.gw!.Address.ToString())
            .FirstOrDefault();
    }
}
