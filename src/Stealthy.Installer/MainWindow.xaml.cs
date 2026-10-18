using System;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Media;
using System.Windows.Threading;

namespace Stealthy.Installer
{
    public partial class MainWindow : Window
    {
        public MainWindow()
        {
            InitializeComponent();

            // Catch all unhandled exceptions and show a real error dialog
            AppDomain.CurrentDomain.UnhandledException += (s, args) =>
            {
                var ex = args.ExceptionObject as Exception;
                MessageBox.Show($"Fatal error: {ex?.GetType().Name}\n\n{ex?.Message}\n\n{ex?.StackTrace}",
                    "Stealthy Installer Error", MessageBoxButton.OK, MessageBoxImage.Error);
            };

            Application.Current.DispatcherUnhandledException += (s, args) =>
            {
                MessageBox.Show($"UI error: {args.Exception.GetType().Name}\n\n{args.Exception.Message}\n\n{args.Exception.StackTrace}",
                    "Stealthy Installer Error", MessageBoxButton.OK, MessageBoxImage.Error);
                args.Handled = true;
            };
        }

        private async void InstallButton_Click(object sender, RoutedEventArgs e)
        {
            InstallButton.Visibility = Visibility.Collapsed;
            ProgressBar.Visibility = Visibility.Visible;
            StepText.Visibility = Visibility.Visible;
            ProgressBar.IsIndeterminate = true;
            StatusText.Text = "Installing...";
            StepText.Text = "Preparing...";

            await Task.Run(PerformInstallation);
        }

        private void SetStatus(string status, string step = "")
        {
            Dispatcher.Invoke(() =>
            {
                StatusText.Text = status;
                StepText.Text = step;
            });
        }

        private void PerformInstallation()
        {
            try
            {
                string targetDir = @"C:\Program Files\Stealthy VPN";

                // Step 0: Terminate running instances to avoid locked files
                SetStatus("Closing running instances...", "Step 1 of 5");
                string[] runningNames = new[] { "OverREALITY.UI", "OverREALITY.Helper", "sing-box" };
                foreach (var name in runningNames)
                {
                    try
                    {
                        foreach (var p in Process.GetProcessesByName(name))
                        {
                            p.Kill();
                            p.WaitForExit(3000);
                        }
                    }
                    catch { }
                }

                // Step 1: Create target directory
                SetStatus("Creating installation directory...", "Step 2 of 5");
                if (!Directory.Exists(targetDir))
                    Directory.CreateDirectory(targetDir);

                // Step 2: Extract embedded payload
                SetStatus("Extracting files...", "Step 3 of 5");
                string tempZip = Path.Combine(Path.GetTempPath(), $"stealthy_payload_{Guid.NewGuid()}.zip");

                var asm = Assembly.GetExecutingAssembly();
                var resources = asm.GetManifestResourceNames();
                string? resourceName = null;
                foreach (var r in resources)
                {
                    if (r.EndsWith("payload.zip", StringComparison.OrdinalIgnoreCase))
                    {
                        resourceName = r;
                        break;
                    }
                }

                if (resourceName == null)
                {
                    throw new Exception($"Payload resource not found. Available resources: {string.Join(", ", resources)}");
                }

                using (var resourceStream = asm.GetManifestResourceStream(resourceName)!)
                using (var fileStream = new FileStream(tempZip, FileMode.Create, FileAccess.Write))
                {
                    resourceStream.CopyTo(fileStream);
                }

                // Step 3: Extract ZIP
                SetStatus("Installing Stealthy VPN...", "Step 4 of 5");
                ZipFile.ExtractToDirectory(tempZip, targetDir, overwriteFiles: true);
                File.Delete(tempZip);

                // Step 4: Create shortcuts
                SetStatus("Creating shortcuts...", "Step 5 of 5");
                string exePath = Path.Combine(targetDir, "OverREALITY.UI.exe");
                string desktopPath = Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory);
                string programsPath = Environment.GetFolderPath(Environment.SpecialFolder.Programs);

                CreateShortcut(exePath, targetDir, Path.Combine(desktopPath, "Stealthy VPN.lnk"));
                CreateShortcut(exePath, targetDir, Path.Combine(programsPath, "Stealthy VPN.lnk"));

                // Done
                Dispatcher.Invoke(() =>
                {
                    ProgressBar.IsIndeterminate = false;
                    ProgressBar.Value = 100;
                    StatusText.Text = "Installation complete!";
                    StepText.Text = "Stealthy VPN is ready to use.";
                    StatusText.Foreground = new SolidColorBrush(Color.FromRgb(0x76, 0xFF, 0x03));
                    LaunchButton.Visibility = Visibility.Visible;
                });
            }
            catch (Exception ex)
            {
                Dispatcher.Invoke(() =>
                {
                    ProgressBar.Visibility = Visibility.Collapsed;
                    StepText.Visibility = Visibility.Collapsed;
                    StatusText.Text = $"Error: {ex.Message}";
                    StatusText.Foreground = new SolidColorBrush(Colors.OrangeRed);
                    InstallButton.Visibility = Visibility.Visible;
                    
                    MessageBox.Show($"Installation failed.\n\nError: {ex.Message}\n\nDetails:\n{ex.StackTrace}",
                        "Installation Error", MessageBoxButton.OK, MessageBoxImage.Error);
                });
            }
        }

        private void CreateShortcut(string targetPath, string workingDir, string shortcutPath)
        {
            string psScript = $@"
$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut('{shortcutPath.Replace("'", "''")}')
$s.TargetPath = '{targetPath.Replace("'", "''")}' 
$s.WorkingDirectory = '{workingDir.Replace("'", "''")}' 
$s.Save()
";
            string scriptFile = Path.Combine(Path.GetTempPath(), $"stealthy_shortcut_{Guid.NewGuid()}.ps1");
            File.WriteAllText(scriptFile, psScript);

            var proc = new Process
            {
                StartInfo = new ProcessStartInfo
                {
                    FileName = "powershell.exe",
                    Arguments = $"-NoProfile -ExecutionPolicy Bypass -File \"{scriptFile}\"",
                    CreateNoWindow = true,
                    UseShellExecute = false,
                    RedirectStandardError = true,
                    RedirectStandardOutput = true
                }
            };
            proc.Start();
            proc.WaitForExit();
            
            try { File.Delete(scriptFile); } catch { }
        }

        private void LaunchButton_Click(object sender, RoutedEventArgs e)
        {
            string exePath = @"C:\Program Files\Stealthy VPN\OverREALITY.UI.exe";
            if (File.Exists(exePath))
            {
                Process.Start(new ProcessStartInfo(exePath) { UseShellExecute = true });
            }
            Application.Current.Shutdown();
        }
    }
}
