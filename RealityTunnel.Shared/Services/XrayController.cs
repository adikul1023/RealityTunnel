using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.NetworkInformation;
using System.Net.Sockets;
using System.Reflection;
using System.Threading;
using RealityTunnel.Models;
using RealityTunnel.Services;

namespace RealityTunnel;

public class XrayController : IXrayController
{
    private Process? _process;
    private string?  _serverIp;
    private string?  _realGateway;

    private const string TunGateway  = "10.0.85.1";
    private const string TunAddress  = "10.0.85.2";
    private const string AdapterName = "singbox_tun";

    public void Start(VpnProfile profile)
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

        _realGateway = GetDefaultGateway()
            ?? throw new InvalidOperationException("Cannot determine default gateway.");
            
        // Resolve hostname to IP for routing purposes
        var addresses = Dns.GetHostAddresses(profile.ServerHost);
        if (addresses == null || addresses.Length == 0)
        {
            throw new InvalidOperationException($"Could not resolve {profile.ServerHost}");
        }
        _serverIp = addresses[0].ToString();

        string config = File.ReadAllText(templatePath)
            .Replace("{{SERVER_HOST}}", profile.ServerHost)
            .Replace("{{SERVER_PORT}}", profile.ServerPort.ToString())
            .Replace("{{VPN_UUID}}", profile.Uuid)
            .Replace("{{VPN_SNI}}", profile.Sni)
            .Replace("{{VPN_PUBLIC_KEY}}", profile.PublicKey)
            .Replace("{{VPN_SHORT_ID}}", profile.ShortId);
            
        File.WriteAllText(configPath, config);

        foreach (var orphan in Process.GetProcessesByName("sing-box"))
        {
            try { orphan.Kill(entireProcessTree: true); orphan.WaitForExit(3000); } catch { }
            orphan.Dispose();
        }

        string wintunPath = Path.Combine(appDir, "wintun.dll");
        string hash = "(not found)", version = "(not found)";
        if (File.Exists(corePath))
        {
            using var sha256 = System.Security.Cryptography.SHA256.Create();
            using var stream = File.OpenRead(corePath);
            hash = BitConverter.ToString(sha256.ComputeHash(stream)).Replace("-", "").ToLowerInvariant();
            version = FileVersionInfo.GetVersionInfo(corePath).FileVersion ?? "(none)";
        }
        string traceLog = Path.Combine(appDir, "runtime_trace.log");
        File.AppendAllText(traceLog, "\n=== Launching sing-box ===\n");
        File.AppendAllText(traceLog, $"Full path to sing-box.exe: {corePath}\nSHA256 hash: {hash}\nFile version: {version}\n");
        File.AppendAllText(traceLog, $"Working directory: {appDir}\nCurrent directory: {Environment.CurrentDirectory}\nConfig.json path: {configPath}\n");
        File.AppendAllText(traceLog, $"File.Exists(sing-box.exe): {File.Exists(corePath)}\n");
        File.AppendAllText(traceLog, $"File.Exists(config.json): {File.Exists(configPath)}\n");
        File.AppendAllText(traceLog, $"File.Exists(wintun.dll): {File.Exists(wintunPath)}\n");
        
        try
        {
            var whoami = Process.Start(new ProcessStartInfo { FileName = "whoami", Arguments = "/groups", RedirectStandardOutput = true, UseShellExecute = false, CreateNoWindow = true });
            if (whoami != null)
            {
                string whoamiOut = whoami.StandardOutput.ReadToEnd();
                whoami.WaitForExit();
                File.AppendAllText(traceLog, $"\n--- whoami /groups ---\n{whoamiOut}\n----------------------\n");
            }
        } catch { }

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

        string stdOut = "", stdErr = "";
        _process.OutputDataReceived += (s, e) => { if (e.Data != null) stdOut += e.Data + "\n"; };
        _process.ErrorDataReceived += (s, e) => { if (e.Data != null) stdErr += e.Data + "\n"; };
        _process.BeginOutputReadLine();
        _process.BeginErrorReadLine();

        Thread.Sleep(4000);

        if (_process.HasExited)
        {
            File.AppendAllText(traceLog, $"Process exited immediately! Code: {_process.ExitCode}\nSTDOUT:\n{stdOut}\nSTDERR:\n{stdErr}\n");
            _process.Dispose();
            _process = null;
            string log = File.Exists(logPath) ? File.ReadAllText(logPath).Trim() : "(no log)";
            throw new InvalidOperationException($"sing-box exited immediately.\n\nStderr:\n{stdErr}\n\nLog:\n{log}");
        }

        try   { SetupRoutes(_serverIp); }
        catch { Stop(); throw; }
    }

    public void Stop()
    {
        try { TeardownRoutes(); } catch { }

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

    private void SetupRoutes(string serverIp)
    {
        RunCmd("netsh", $"interface ip set address \"{AdapterName}\" static {TunAddress} 255.255.255.0");
        RunCmd("netsh", $"interface ip set dns name=\"{AdapterName}\" static 8.8.8.8 validate=no");
        RunCmd("netsh", $"interface ip add dns name=\"{AdapterName}\" 8.8.4.4 index=2 validate=no");
        RunCmd("route", $"add {serverIp} mask 255.255.255.255 {_realGateway} metric 5");
        RunCmd("route", $"add 0.0.0.0 mask 128.0.0.0 {TunGateway} metric 6");
        RunCmd("route", $"add 128.0.0.0 mask 128.0.0.0 {TunGateway} metric 6");
    }

    private void TeardownRoutes()
    {
        if (!string.IsNullOrEmpty(_serverIp))
            try { RunCmd("route", $"delete {_serverIp} mask 255.255.255.255"); } catch { }
        try { RunCmd("route", $"delete 0.0.0.0 mask 128.0.0.0 {TunGateway}"); } catch { }
        try { RunCmd("route", $"delete 128.0.0.0 mask 128.0.0.0 {TunGateway}"); } catch { }
    }

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
