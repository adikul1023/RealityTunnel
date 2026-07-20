using System;
using System.Diagnostics;
using System.IO.Pipes;
using System.Runtime.InteropServices;
using System.Security.AccessControl;
using System.Security.Principal;
using System.Text;

namespace RealityTunnel.Helper;

public class PipeSecurityHelper
{
    private readonly HelperLogger _logger;

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool GetNamedPipeClientProcessId(IntPtr Pipe, out uint ClientProcessId);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern IntPtr OpenProcess(uint dwDesiredAccess, bool bInheritHandle, uint dwProcessId);

    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Auto)]
    private static extern bool QueryFullProcessImageName(IntPtr hProcess, uint dwFlags, [Out] StringBuilder lpExeName, ref uint lpdwSize);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool CloseHandle(IntPtr hObject);

    private const uint PROCESS_QUERY_LIMITED_INFORMATION = 0x1000;

    public PipeSecurityHelper(HelperLogger logger)
    {
        _logger = logger;
    }

    public PipeSecurity CreatePipeSecurity()
    {
        var pipeSecurity = new PipeSecurity();

        // Grant FullControl to current process owner so service/test host can create multiple instances
        using (var currentIdentity = WindowsIdentity.GetCurrent())
        {
            if (currentIdentity.User != null)
            {
                pipeSecurity.AddAccessRule(new PipeAccessRule(currentIdentity.User, PipeAccessRights.FullControl, AccessControlType.Allow));
            }
        }

        // Grant FullControl to BUILTIN\Administrators and LocalSystem
        var adminsSid = new SecurityIdentifier(WellKnownSidType.BuiltinAdministratorsSid, null);
        pipeSecurity.AddAccessRule(new PipeAccessRule(adminsSid, PipeAccessRights.FullControl, AccessControlType.Allow));

        var systemSid = new SecurityIdentifier(WellKnownSidType.LocalSystemSid, null);
        pipeSecurity.AddAccessRule(new PipeAccessRule(systemSid, PipeAccessRights.FullControl, AccessControlType.Allow));

        // Grant ReadWrite access to Interactive users locally logged on (NT AUTHORITY\INTERACTIVE, S-1-5-4) for client connections
        var interactiveSid = new SecurityIdentifier(WellKnownSidType.InteractiveSid, null);
        pipeSecurity.AddAccessRule(new PipeAccessRule(interactiveSid, PipeAccessRights.ReadWrite, AccessControlType.Allow));

        return pipeSecurity;
    }

    public bool ValidateClientConnection(NamedPipeServerStream pipeStream, out string clientIdentity, out uint clientPid, out string clientProcessPath)
    {
        clientIdentity = "Unknown";
        clientPid = 0;
        clientProcessPath = "Unknown";

        try
        {
            if (pipeStream.SafePipeHandle.IsInvalid)
            {
                _logger.LogWarn("Pipe handle is invalid during client validation.");
                return false;
            }

            if (GetNamedPipeClientProcessId(pipeStream.SafePipeHandle.DangerousGetHandle(), out uint pid))
            {
                clientPid = pid;
                clientProcessPath = GetProcessImagePath(pid);
            }

            // Impersonate client to inspect Windows Security Token
            string impersonatedIdentity = "Unknown";
            pipeStream.RunAsClient(() =>
            {
                using var identity = WindowsIdentity.GetCurrent();
                impersonatedIdentity = identity.Name;

                if (identity.IsAnonymous || identity.IsGuest)
                {
                    throw new UnauthorizedAccessException("Anonymous/Guest connections are rejected.");
                }
            });

            clientIdentity = impersonatedIdentity;
            _logger.LogInfo($"Verified client connection: User='{clientIdentity}', PID={clientPid}, Path='{clientProcessPath}'");
            return true;
        }
        catch (Exception ex)
        {
            _logger.LogError("Failed to validate client token and identity over pipe.", ex);
            return false;
        }
    }

    private static string GetProcessImagePath(uint pid)
    {
        if (pid == 0) return "Unknown";
        IntPtr hProcess = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, false, pid);
        if (hProcess == IntPtr.Zero) return $"Unknown (PID {pid})";

        try
        {
            var buffer = new StringBuilder(1024);
            uint size = (uint)buffer.Capacity;
            if (QueryFullProcessImageName(hProcess, 0, buffer, ref size))
            {
                return buffer.ToString();
            }
            return $"Unknown (PID {pid})";
        }
        finally
        {
            CloseHandle(hProcess);
        }
    }
}
