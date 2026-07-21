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
        Console.Title = "Stealthy Client Setup";
        Console.ForegroundColor = ConsoleColor.Cyan;
        Console.WriteLine("=================================================");
        Console.WriteLine("          Stealthy VPN Client Setup           ");
        Console.WriteLine("=================================================");
        Console.ResetColor();
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
            var assembly = Assembly.GetExecutingAssembly();
            string resourceName = assembly.GetManifestResourceNames()
                .FirstOrDefault(n => n.EndsWith("payload.zip"))
                ?? throw new InvalidOperationException("Embedded payload.zip resource not found.");

            using Stream? zipStream = assembly.GetManifestResourceStream(resourceName);
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

        // 3. Prompt or read credentials for .env
        string uuid = args.FirstOrDefault(a => a.StartsWith("--uuid=", StringComparison.OrdinalIgnoreCase))?.Substring("--uuid=".Length).Trim() ?? "";
        string publicKey = args.FirstOrDefault(a => a.StartsWith("--key=", StringComparison.OrdinalIgnoreCase))?.Substring("--key=".Length).Trim() ?? "";
        string sni = args.FirstOrDefault(a => a.StartsWith("--sni=", StringComparison.OrdinalIgnoreCase))?.Substring("--sni=".Length).Trim() ?? "dl.google.com";
        string shortId = args.FirstOrDefault(a => a.StartsWith("--shortid=", StringComparison.OrdinalIgnoreCase))?.Substring("--shortid=".Length).Trim() ?? "";

        if (!isSilent && (string.IsNullOrWhiteSpace(uuid) || string.IsNullOrWhiteSpace(publicKey)))
        {
            Console.WriteLine("\n-------------------------------------------------");
            Console.ForegroundColor = ConsoleColor.Cyan;
            Console.WriteLine("          Configure VPN Connection details       ");
            Console.ResetColor();
            Console.WriteLine("-------------------------------------------------");

            while (string.IsNullOrWhiteSpace(uuid))
            {
                Console.Write("Enter VLESS UUID (required): ");
                uuid = Console.ReadLine()?.Trim() ?? "";
            }

            while (string.IsNullOrWhiteSpace(publicKey))
            {
                Console.Write("Enter REALITY Public Key (required): ");
                publicKey = Console.ReadLine()?.Trim() ?? "";
            }

            Console.Write("Enter VPN SNI (default: dl.google.com): ");
            string inputSni = Console.ReadLine()?.Trim() ?? "";
            if (!string.IsNullOrWhiteSpace(inputSni)) { sni = inputSni; }

            Console.Write("Enter Short ID (optional): ");
            shortId = Console.ReadLine()?.Trim() ?? "";
        }

        if (!string.IsNullOrWhiteSpace(uuid) && !string.IsNullOrWhiteSpace(publicKey))
        {
            try
            {
                string envContent =
                    $"# Stealthy — server credentials\n" +
                    $"# Keep this file private. Never commit it to git.\n\n" +
                    $"VPN_UUID={uuid}\n" +
                    $"VPN_PUBLIC_KEY={publicKey}\n" +
                    $"VPN_SNI={sni}\n" +
                    $"VPN_SHORT_ID={shortId}\n";

                string envPath = Path.Combine(installDir, ".env");
                File.WriteAllText(envPath, envContent);

                Console.ForegroundColor = ConsoleColor.Green;
                Console.WriteLine("\nConfiguration credentials successfully saved to .env!");
                Console.ResetColor();
            }
            catch (Exception ex)
            {
                Console.ForegroundColor = ConsoleColor.Red;
                Console.WriteLine($"Error writing configuration: {ex.Message}");
                Console.ResetColor();
            }
        }

        // 4. Create Desktop Shortcut
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

        // 5. Register and start RealityTunnelHelper Windows Service
        RegisterAndStartService(installDir);

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

    private static void RegisterAndStartService(string installDir)
    {
        string helperExePath = Path.Combine(installDir, "RealityTunnel.Helper.exe");
        if (!File.Exists(helperExePath))
        {
            Console.ForegroundColor = ConsoleColor.Yellow;
            Console.WriteLine($"\nHelper service executable ({helperExePath}) not found in extracted payload. Skipping service registration.");
            Console.ResetColor();
            return;
        }

        Console.WriteLine("\nRegistering and starting RealityTunnelHelper Windows Service...");
        StopAndRemoveService();

        string binPath = $"\"{helperExePath}\"";
        RunScCommand($"create RealityTunnelHelper binPath= \"{binPath}\" start= auto obj= LocalSystem");
        RunScCommand("start RealityTunnelHelper");
    }

    private static void StopAndRemoveService()
    {
        RunScCommand("stop RealityTunnelHelper");
        RunScCommand("delete RealityTunnelHelper");
    }

    private static void RunScCommand(string args)
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
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Warning running sc.exe {args}: {ex.Message}");
        }
    }
}
