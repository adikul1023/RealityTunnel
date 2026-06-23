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
        Console.Title = "OverREALITY Client Setup";
        Console.ForegroundColor = ConsoleColor.Cyan;
        Console.WriteLine("=================================================");
        Console.WriteLine("          OverREALITY VPN Client Setup           ");
        Console.WriteLine("=================================================");
        Console.ResetColor();
        Console.WriteLine();

        // 1. Resolve installation directory
        string defaultPath = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "Programs",
            "OverREALITY"
        );

        Console.WriteLine($"Default installation path: \n{defaultPath}");
        Console.Write("\nPress Enter to accept default, or enter a custom folder path: ");
        string inputPath = Console.ReadLine()?.Trim() ?? "";
        
        string installDir = defaultPath;
        if (!string.IsNullOrEmpty(inputPath))
        {
            // Expand environment variables like %LocalAppData% if the user uses them
            installDir = Environment.ExpandEnvironmentVariables(inputPath);
        }

        Console.ForegroundColor = ConsoleColor.Yellow;
        Console.WriteLine($"\nInstalling to: {installDir}");
        Console.ResetColor();

        try
        {
            // Create directory if it doesn't exist
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
            Console.WriteLine("\nPress any key to exit...");
            Console.ReadKey();
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
                
                // Create directory for the entry if it's a directory
                string? dir = Path.GetDirectoryName(destinationPath);
                if (dir != null && !Directory.Exists(dir))
                {
                    Directory.CreateDirectory(dir);
                }

                if (!string.IsNullOrEmpty(entry.Name)) // It's a file, not a directory entry
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
            Console.WriteLine("\nPress any key to exit...");
            Console.ReadKey();
            return;
        }

        // 3. Prompt for VPN credentials to write .env
        Console.WriteLine("\n-------------------------------------------------");
        Console.ForegroundColor = ConsoleColor.Cyan;
        Console.WriteLine("          Configure VPN Connection details       ");
        Console.ResetColor();
        Console.WriteLine("-------------------------------------------------");

        string uuid = "";
        while (string.IsNullOrWhiteSpace(uuid))
        {
            Console.Write("Enter VLESS UUID (required): ");
            uuid = Console.ReadLine()?.Trim() ?? "";
            if (string.IsNullOrWhiteSpace(uuid))
            {
                Console.ForegroundColor = ConsoleColor.Red;
                Console.WriteLine("UUID cannot be empty!");
                Console.ResetColor();
            }
        }

        string publicKey = "";
        while (string.IsNullOrWhiteSpace(publicKey))
        {
            Console.Write("Enter REALITY Public Key (required): ");
            publicKey = Console.ReadLine()?.Trim() ?? "";
            if (string.IsNullOrWhiteSpace(publicKey))
            {
                Console.ForegroundColor = ConsoleColor.Red;
                Console.WriteLine("Public Key cannot be empty!");
                Console.ResetColor();
            }
        }

        Console.Write("Enter VPN SNI (default: dl.google.com): ");
        string sni = Console.ReadLine()?.Trim() ?? "";
        if (string.IsNullOrWhiteSpace(sni))
        {
            sni = "dl.google.com";
        }

        Console.Write("Enter Short ID (optional): ");
        string shortId = Console.ReadLine()?.Trim() ?? "";

        // Write .env file
        try
        {
            string envContent = 
                $"# OverREALITY — server credentials\n" +
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

        // 4. Create Desktop Shortcut
        Console.WriteLine("\nCreating Desktop shortcut...");
        try
        {
            string desktopDir = Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory);
            string shortcutPath = Path.Combine(desktopDir, "OverREALITY.lnk");
            string targetPath = Path.Combine(installDir, "RealityTunnel.exe");

            // Write shortcut using PowerShell script
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

        Console.WriteLine("\n=================================================");
        Console.ForegroundColor = ConsoleColor.Green;
        Console.WriteLine("        Installation Completed Successfully!     ");
        Console.ResetColor();
        Console.WriteLine("=================================================");
        Console.WriteLine("\nYou can now double-click the 'OverREALITY' shortcut on your Desktop to run the app.");
        Console.WriteLine("\nPress any key to exit...");
        Console.ReadKey();
    }
}
