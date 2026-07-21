using System;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Reflection;

namespace RealityTunnelSetup;

class Program
{
    static void Main(string[] args)
    {
        Console.Title = "RealityTunnel Installer";
        Console.ForegroundColor = ConsoleColor.Cyan;
        Console.WriteLine("=================================================");
        Console.WriteLine("             RealityTunnel Installer             ");
        Console.WriteLine("=================================================");
        Console.ResetColor();

        var assembly = Assembly.GetExecutingAssembly();
        string version = assembly.GetName().Version?.ToString(3) ?? "1.0.0";
        var metadata = assembly.GetCustomAttributes<AssemblyMetadataAttribute>();
        string commit = metadata.FirstOrDefault(a => a.Key == "GitCommit")?.Value ?? "unknown";
        if (string.IsNullOrWhiteSpace(commit)) commit = "unknown";
        string built = metadata.FirstOrDefault(a => a.Key == "BuildDate")?.Value ?? "unknown";
        if (string.IsNullOrWhiteSpace(built)) built = DateTime.Now.ToString("yyyy-MM-dd");

        Console.WriteLine($"Version: {version}");
        Console.WriteLine($"Commit:  {commit}");
        Console.WriteLine($"Built:   {built}");
        Console.WriteLine("=================================================");
        Console.WriteLine();

        bool isUninstall = args.Contains("--uninstall", StringComparer.OrdinalIgnoreCase) || args.Contains("-uninstall", StringComparer.OrdinalIgnoreCase);
        bool isSilent = args.Contains("--silent", StringComparer.OrdinalIgnoreCase) || args.Contains("--unattended", StringComparer.OrdinalIgnoreCase);

        string defaultPath = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "Programs",
            "OverREALITY"
        );

        string installDir = defaultPath;
        var dirArg = args.FirstOrDefault(a => a.StartsWith("--dir=", StringComparison.OrdinalIgnoreCase));
        if (dirArg != null)
        {
            installDir = Environment.ExpandEnvironmentVariables(dirArg.Substring("--dir=".Length).Trim());
        }

        if (isUninstall)
        {
            Console.ForegroundColor = ConsoleColor.Yellow;
            Console.WriteLine($"\nUninstalling from: {installDir}");
            Console.ResetColor();

            StopAndRemoveService();

            try
            {
                string desktopDir = Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory);
                string shortcutPath = Path.Combine(desktopDir, "Stealthy.lnk");
                if (File.Exists(shortcutPath))
                {
                    File.Delete(shortcutPath);
                    Console.WriteLine("Removed Desktop shortcut.");
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Warning removing shortcut: {ex.Message}");
            }

            try
            {
                if (Directory.Exists(installDir))
                {
                    Directory.Delete(installDir, true);
                    Console.WriteLine($"Removed directory: {installDir}");
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Warning removing directory: {ex.Message}");
            }

            Console.ForegroundColor = ConsoleColor.Green;
            Console.WriteLine("\nUninstallation Completed Successfully!");
            Console.ResetColor();

            if (!isSilent)
            {
                Console.WriteLine("\nPress any key to exit...");
                Console.ReadKey();
            }
            return;
        }

        // 1. Resolve installation directory
        if (!isSilent && dirArg == null)
        {
            Console.WriteLine($"Default installation path: \n{defaultPath}");
            Console.Write("\nPress Enter to accept default, or enter a custom folder path: ");
            string inputPath = Console.ReadLine()?.Trim() ?? "";
            if (!string.IsNullOrEmpty(inputPath))
            {
                installDir = Environment.ExpandEnvironmentVariables(inputPath);
            }
        }

        Console.ForegroundColor = ConsoleColor.Yellow;
        Console.WriteLine($"\nInstalling to: {installDir}");
        Console.ResetColor();

        try
        {
            if (!Directory.Exists(installDir))
            {
                Directory.CreateDirectory(installDir);
            }
        }
        catch (Exception ex)
        {
            Console.ForegroundColor = ConsoleColor.Red;
            Console.WriteLine($"Error creating directory: {ex.Message}");
            Console.ResetColor();
            if (!isSilent) { Console.WriteLine("\nPress any key to exit..."); Console.ReadKey(); }
            return;
        }

        // 2. Extract embedded payload.zip
        Console.WriteLine("\nExtracting client files...");
        try
        {
            var execAssembly = Assembly.GetExecutingAssembly();
            string resourceName = execAssembly.GetManifestResourceNames()
                .FirstOrDefault(n => n.EndsWith("payload.zip"))
                ?? throw new InvalidOperationException("Embedded payload.zip resource not found.");

            using Stream? zipStream = execAssembly.GetManifestResourceStream(resourceName);
            if (zipStream == null)
            {
                throw new InvalidOperationException("Failed to open embedded payload stream.");
            }

            using var archive = new ZipArchive(zipStream, ZipArchiveMode.Read);
            foreach (var entry in archive.Entries)
            {
                string destinationPath = Path.Combine(installDir, entry.FullName);
                string? dir = Path.GetDirectoryName(destinationPath);
                if (dir != null && !Directory.Exists(dir))
                {
                    Directory.CreateDirectory(dir);
                }

                if (!string.IsNullOrEmpty(entry.Name))
                {
                    entry.ExtractToFile(destinationPath, overwrite: true);
                    Console.WriteLine($"  Extracted: {entry.FullName}");
                }
            }
            Console.ForegroundColor = ConsoleColor.Green;
            Console.WriteLine("Extraction complete!");
            Console.ResetColor();
        }
        catch (Exception ex)
        {
            Console.ForegroundColor = ConsoleColor.Red;
            Console.WriteLine($"Extraction failed: {ex.Message}");
            Console.ResetColor();
            if (!isSilent) { Console.WriteLine("\nPress any key to exit..."); Console.ReadKey(); }
            return;
        }

        // 3. Create Desktop Shortcut
        Console.WriteLine("\nCreating Desktop shortcut...");
        try
        {
            string desktopDir = Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory);
            string shortcutPath = Path.Combine(desktopDir, "Stealthy.lnk");
            string targetPath = Path.Combine(installDir, "RealityTunnel.exe");

            string psCode = $"$WshShell = New-Object -ComObject WScript.Shell; " +
                            $"$Shortcut = $WshShell.CreateShortcut('{shortcutPath.Replace("'", "''")}'); " +
                            $"$Shortcut.TargetPath = '{targetPath.Replace("'", "''")}'; " +
                            $"$Shortcut.WorkingDirectory = '{installDir.Replace("'", "''")}'; " +
                            $"$Shortcut.IconLocation = '{targetPath.Replace("'", "''")},0'; " +
                            $"$Shortcut.Save()";

            var startInfo = new ProcessStartInfo
            {
                FileName = "powershell.exe",
                Arguments = $"-NoProfile -ExecutionPolicy Bypass -Command \"{psCode}\"",
                CreateNoWindow = true,
                UseShellExecute = false
            };

            using var p = Process.Start(startInfo);
            p?.WaitForExit();

            Console.ForegroundColor = ConsoleColor.Green;
            Console.WriteLine("Desktop shortcut created successfully!");
            Console.ResetColor();
        }
        catch (Exception ex)
        {
            Console.ForegroundColor = ConsoleColor.Red;
            Console.WriteLine($"Error creating shortcut: {ex.Message}");
            Console.ResetColor();
        }

        // 4. Register and start RealityTunnelHelper Windows Service
        if (!RegisterAndStartService(installDir))
        {
            Console.WriteLine("\n=================================================");
            Console.ForegroundColor = ConsoleColor.Red;
            Console.WriteLine("              Installation Failed                ");
            Console.ResetColor();
            Console.WriteLine("=================================================");
            Console.WriteLine("\nRealityTunnelHelper could not be started as a Windows Service.");
            if (!isSilent)
            {
                Console.WriteLine("\nPress any key to exit...");
                Console.ReadKey();
            }
            Environment.Exit(1);
            return;
        }

        Console.WriteLine("\n=================================================");
        Console.ForegroundColor = ConsoleColor.Green;
        Console.WriteLine("        Installation Completed Successfully!     ");
        Console.ResetColor();
        Console.WriteLine("=================================================");
        Console.WriteLine("\nYou can now double-click the 'Stealthy' shortcut on your Desktop to run the app.");
        if (!isSilent)
        {
            Console.WriteLine("\nPress any key to exit...");
            Console.ReadKey();
        }
    }

    private static bool RegisterAndStartService(string installDir)
    {
        string helperExePath = Path.Combine(installDir, "RealityTunnel.Helper.exe");
        if (!File.Exists(helperExePath))
        {
            Console.ForegroundColor = ConsoleColor.Yellow;
            Console.WriteLine($"\nHelper service executable ({helperExePath}) not found in extracted payload. Skipping service registration.");
            Console.ResetColor();
            return false;
        }

        Console.WriteLine("\nRegistering and starting RealityTunnelHelper Windows Service...");
        StopAndRemoveService();

        string binPath = $"\"{helperExePath}\"";
        bool createSuccess = RunScCommand($"create RealityTunnelHelper binPath= \"{binPath}\" start= auto obj= LocalSystem");
        if (!createSuccess)
        {
            Console.ForegroundColor = ConsoleColor.Red;
            Console.WriteLine("  sc create RealityTunnelHelper failed.");
            Console.ResetColor();
            return false;
        }

        bool startSuccess = RunScCommand("start RealityTunnelHelper");
        if (!startSuccess)
        {
            Console.ForegroundColor = ConsoleColor.Red;
            Console.WriteLine("  sc start RealityTunnelHelper failed.");
            Console.ResetColor();
            return false;
        }

        return true;
    }

    private static void StopAndRemoveService()
    {
        RunScCommand("stop RealityTunnelHelper", ignoreError: true);
        RunScCommand("delete RealityTunnelHelper", ignoreError: true);
    }

    private static bool RunScCommand(string args, bool ignoreError = false)
    {
        try
        {
            var startInfo = new ProcessStartInfo
            {
                FileName = "sc.exe",
                Arguments = args,
                CreateNoWindow = true,
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true
            };
            using var p = Process.Start(startInfo);
            if (p != null)
            {
                string outStr = p.StandardOutput.ReadToEnd();
                string errStr = p.StandardError.ReadToEnd();
                p.WaitForExit();
                if (!string.IsNullOrWhiteSpace(outStr)) { Console.WriteLine($"  sc {args} -> {outStr.Trim()}"); }
                if (!string.IsNullOrWhiteSpace(errStr)) { Console.WriteLine($"  sc {args} [err] -> {errStr.Trim()}"); }

                if (p.ExitCode != 0 || outStr.Contains("FAILED", StringComparison.OrdinalIgnoreCase) || errStr.Contains("FAILED", StringComparison.OrdinalIgnoreCase))
                {
                    return ignoreError;
                }
                return true;
            }
        }
        catch (Exception ex)
        {
            if (!ignoreError)
            {
                Console.WriteLine($"Warning running sc.exe {args}: {ex.Message}");
            }
        }
        return false;
    }
}
