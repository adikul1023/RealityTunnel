using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Net.NetworkInformation;
using System.Net.Sockets;
using System.Reflection;
using System.Threading;

namespace RealityTunnel;

public class XrayController
{
    private Process? _process;
    private string?  _serverIp;
    private string?  _realGateway;

    private const string TunGateway  = "10.0.85.1";
    private const string TunAddress  = "10.0.85.2";
    private const string TunMask     = "255.255.255.0";
    private const string AdapterName = "singbox_tun";

    public void Start(string serverIp)
    {
        if (IsRunning())
            throw new InvalidOperationException("Already running.");

        string appDir       = GetAppDirectory();
        string corePath     = Path.Combine(appDir, "sing-box.exe");
        string templatePath = Path.Combine(appDir, "config.template.json");
        string configPath   = Path.Combine(appDir, "config.json");
        string logPath      = Path.Combine(appDir, "singbox.log");

        if (!File.Exists(corePath))
            throw new FileNotFoundException(
                "sing-box.exe not found in app directory.\n" +
                "Download: https://github.com/SagerNet/sing-box/releases");
        if (!File.Exists(templatePath))
            throw new FileNotFoundException("config.template.json not found.");

        // Capture real gateway BEFORE any routing changes
        _realGateway = GetDefaultGateway()
            ?? throw new InvalidOperationException("Cannot determine default gateway.");
        _serverIp = serverIp;

        var envVars = LoadDotEnv(appDir);
        string config = File.ReadAllText(templatePath).Replace("{{SERVER_IP}}", serverIp);
        foreach (var kv in envVars)
            config = config.Replace($"{{{{{kv.Key}}}}}", kv.Value);
        File.WriteAllText(configPath, config);

        // Kill any orphaned sing-box from previous runs
        foreach (var orphan in Process.GetProcessesByName("sing-box"))
        {
            try { orphan.Kill(entireProcessTree: true); orphan.WaitForExit(3000); } catch { }
            orphan.Dispose();
        }

        // Start sing-box (auto_route disabled — we manage routes manually below)
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

        // Wait for sing-box to create the TUN adapter
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
            // Assign IP to the TUN adapter sing-box created
            RunCmd("netsh", $"interface ip set address \"{AdapterName}\" static {TunAddress} {TunMask}");
            RunCmd("netsh", $"interface ip set dns name=\"{AdapterName}\" static 8.8.8.8 validate=no");
            RunCmd("netsh", $"interface ip add dns name=\"{AdapterName}\" 8.8.4.4 index=2 validate=no");

            // Server IP bypasses TUN (prevents routing loop)
            RunCmd("route", $"add {serverIp} mask 255.255.255.255 {_realGateway} metric 5");

            // All other traffic goes through TUN (two /1 routes override default route)
            RunCmd("route", $"add 0.0.0.0 mask 128.0.0.0 {TunGateway} metric 6");
            RunCmd("route", $"add 128.0.0.0 mask 128.0.0.0 {TunGateway} metric 6");
        }
        catch
        {
            Stop();
            throw;
        }
    }

    public void Stop()
    {
        if (!string.IsNullOrEmpty(_serverIp))
            try { RunCmd("route", $"delete {_serverIp} mask 255.255.255.255"); } catch { }
        try { RunCmd("route", $"delete 0.0.0.0 mask 128.0.0.0 {TunGateway}"); } catch { }
        try { RunCmd("route", $"delete 128.0.0.0 mask 128.0.0.0 {TunGateway}"); } catch { }

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

    private static string GetAppDirectory()
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

    private static System.Collections.Generic.Dictionary<string, string> LoadDotEnv(string appDir)
    {
        var result = new System.Collections.Generic.Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
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
        // Find the lowest-index active gateway (physical adapter, not WSL/Hyper-V virtual)
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
