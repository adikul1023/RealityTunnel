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
        
        var configPath = Path.Combine(baseDir, "config.json");
        _logger.LogInformation("Attempting: {Path} (WriteAllText)", configPath);
        await File.WriteAllTextAsync(configPath, configJson, cancellationToken);
        _logger.LogInformation("Success: wrote config.json.");

        _logger.LogInformation("Executable: {ExePath}\nConfig file: {ConfigPath}\nWorking directory: {WorkDir}", exePath, configPath, baseDir);

        // Run validation check before launching
        var checkProcess = new Process
        {
            StartInfo = new ProcessStartInfo
            {
                FileName = exePath,
                Arguments = "check -c config.json",
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                CreateNoWindow = true,
                WorkingDirectory = baseDir
            }
        };
        
        checkProcess.Start();
        string checkOutput = await checkProcess.StandardOutput.ReadToEndAsync();
        string checkError = await checkProcess.StandardError.ReadToEndAsync();
        await checkProcess.WaitForExitAsync(cancellationToken);
        
        if (checkProcess.ExitCode != 0)
        {
            _logger.LogError("sing-box config validation failed.\nOutput: {Output}\nError: {Error}", checkOutput, checkError);
            throw new Exception($"Configuration validation failed:\n{checkError}");
        }

        _logger.LogInformation("Config validation passed.");

        _process = new Process
        {
            StartInfo = new ProcessStartInfo
            {
                FileName = exePath,
                Arguments = "run -c config.json",
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                CreateNoWindow = true,
                WorkingDirectory = baseDir
            },
            EnableRaisingEvents = true
        };

        _process.OutputDataReceived += (s, e) => { if (e.Data != null) _logger.LogInformation("[sing-box] {Output}", e.Data); };
        _process.ErrorDataReceived += (s, e) => { if (e.Data != null) _logger.LogError("[sing-box] {Error}", e.Data); };
        _process.Exited += (s, e) => 
        {
            var exitCode = _process.ExitCode;
            var runtime = DateTime.Now - _process.StartTime;
            var unexpected = exitCode != 0 && exitCode != 1; // Depending on what sing-box returns on normal kill
            ProcessExited?.Invoke(this, new ProcessExitedEventArgs(exitCode, runtime, unexpected));
        };

        if (!_process.Start())
        {
            throw new Exception("Failed to start sing-box process.");
        }

        _process.BeginOutputReadLine();
        _process.BeginErrorReadLine();

        _logger.LogInformation("Sing-box process started with ID {ProcessId}", _process.Id);
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
