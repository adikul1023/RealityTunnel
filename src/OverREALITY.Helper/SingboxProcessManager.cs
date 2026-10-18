using System;
using System.Diagnostics;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;

namespace OverREALITY.Helper;

public class SingboxProcessManager : IDisposable
{
    private readonly ILogger<SingboxProcessManager> _logger;
    private Process? _process;

    public event EventHandler<ProcessExitedEventArgs>? ProcessExited;

    public SingboxProcessManager(ILogger<SingboxProcessManager> logger)
    {
        _logger = logger;
    }

    public async Task StartAsync(string configJson, CancellationToken cancellationToken = default)
    {
        if (_process != null && !_process.HasExited)
        {
            throw new InvalidOperationException("Sing-box process is already running.");
        }

        try
        {
            foreach (var p in Process.GetProcessesByName("sing-box"))
            {
                p.Kill();
                p.WaitForExit(1000);
            }
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to kill existing sing-box processes.");
        }

        var baseDir = Path.GetDirectoryName(Environment.ProcessPath) ?? AppContext.BaseDirectory;
        var exePath = Path.Combine(baseDir, "sing-box.exe");
        _logger.LogInformation("Attempting: {Path}", exePath);
        if (!File.Exists(exePath))
        {
            _logger.LogWarning("Failure: sing-box.exe not found at {Path}, falling back to system PATH.", exePath);
            exePath = "sing-box.exe"; 
        }
        else 
        {
            _logger.LogInformation("Success: sing-box.exe found.");
        }
        
        // Store mutable config in ProgramData instead of protected Program Files
        var dataDir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData), "OverREALITY", "singbox");
        if (!Directory.Exists(dataDir))
        {
            Directory.CreateDirectory(dataDir);
        }

        var configPath = Path.Combine(dataDir, "config.json");
        _logger.LogInformation("Writing config to: {Path}", configPath);
        await File.WriteAllTextAsync(configPath, configJson, cancellationToken);
        _logger.LogInformation("Success: wrote config.json.");

        _logger.LogInformation("Executable: {ExePath}\nConfig file: {ConfigPath}\nWorking directory: {WorkDir}", exePath, configPath, dataDir);

        // Run validation check before launching
        var checkProcess = new Process
        {
            StartInfo = new ProcessStartInfo
            {
                FileName = exePath,
                Arguments = $"check -c \"{configPath}\"",
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                CreateNoWindow = true,
                WorkingDirectory = dataDir
            }
        };
        
        checkProcess.Start();
        string checkOutput = await checkProcess.StandardOutput.ReadToEndAsync();
        string checkError = await checkProcess.StandardError.ReadToEndAsync();
        await checkProcess.WaitForExitAsync(cancellationToken);
        
        if (checkProcess.ExitCode != 0)
        {
            _logger.LogError("sing-box config validation failed.\nOutput: {Output}\nError: {Error}", checkOutput, checkError);
            throw new Exception($"Configuration validation failed: {checkError} {checkOutput}".Trim());
        }

        _logger.LogInformation("Config validation passed.");

        _process = new Process
        {
            StartInfo = new ProcessStartInfo
            {
                FileName = exePath,
                Arguments = $"run -c \"{configPath}\"",
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                CreateNoWindow = true,
                WorkingDirectory = dataDir
            },
            EnableRaisingEvents = true
        };

        string lastErrorOutput = string.Empty;
        var errorLock = new object();
        _process.OutputDataReceived += (s, e) => 
        { 
            if (e.Data != null) 
            {
                _logger.LogInformation("[sing-box] {Output}", e.Data); 
                if (e.Data.Contains("FATAL", StringComparison.OrdinalIgnoreCase) || 
                    e.Data.Contains("ERROR", StringComparison.OrdinalIgnoreCase) || 
                    e.Data.Contains("Access is denied", StringComparison.OrdinalIgnoreCase) || 
                    e.Data.Contains("panic", StringComparison.OrdinalIgnoreCase))
                {
                    lock (errorLock) { lastErrorOutput = e.Data; }
                }
            }
        };
        _process.ErrorDataReceived += (s, e) => 
        { 
            if (e.Data != null) 
            {
                _logger.LogError("[sing-box] {Error}", e.Data); 
                lock (errorLock) { lastErrorOutput = e.Data; }
            }
        };
        _process.Exited += (s, e) => 
        {
            var exitCode = _process.ExitCode;
            var runtime = DateTime.Now - _process.StartTime;
            var unexpected = exitCode != 0 && exitCode != 1;
            ProcessExited?.Invoke(this, new ProcessExitedEventArgs(exitCode, runtime, unexpected));
        };

        if (!_process.Start())
        {
            throw new Exception("Failed to start sing-box process.");
        }

        _process.BeginOutputReadLine();
        _process.BeginErrorReadLine();

        _logger.LogInformation("Sing-box process started with ID {ProcessId}", _process.Id);

        // Verification delay to detect immediate crashes (e.g. TUN creation failure or permission denial)
        var exitTask = _process.WaitForExitAsync(cancellationToken);
        var delayTask = Task.Delay(1000, cancellationToken);
        var completed = await Task.WhenAny(exitTask, delayTask);
        if (completed == exitTask)
        {
            var errMsg = string.IsNullOrWhiteSpace(lastErrorOutput) 
                ? $"sing-box exited immediately with code {_process.ExitCode}." 
                : $"sing-box startup failed: {lastErrorOutput}";
            _logger.LogError(errMsg);
            throw new Exception(errMsg);
        }
    }

    public void Stop()
    {
        if (_process != null && !_process.HasExited)
        {
            _logger.LogInformation("Stopping sing-box process.");
            _process.Kill(entireProcessTree: true);
            _process.WaitForExit(5000);
        }
    }

    public void Dispose()
    {
        Stop();
        _process?.Dispose();
    }
}

