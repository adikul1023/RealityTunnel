using System;
using System.IO;
using System.IO.Pipes;
using System.Runtime.InteropServices;
using System.Security.AccessControl;
using System.Security.Principal;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using OverREALITY.Shared.Api.VpnRuntime;

namespace OverREALITY.Helper;

public class IpcServer
{
    private const string PipeName = "OverREALITY_Helper_Pipe_v5";
    private readonly ILogger<IpcServer> _logger;
    private readonly JsonSerializerOptions _jsonOptions;

    public Func<StartVpnRequest, Task<bool>>? OnStartRequested { get; set; }
    public Func<Task<bool>>? OnStopRequested { get; set; }
    public Func<HelperStatus>? OnStatusRequested { get; set; }

    public IpcServer(ILogger<IpcServer> logger)
    {
        _logger = logger;
        _jsonOptions = new JsonSerializerOptions 
        { 
            WriteIndented = false,
            DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
            PropertyNameCaseInsensitive = true
        };
    }

    public async Task StartListeningAsync(CancellationToken cancellationToken)
    {
        _logger.LogInformation("IPC Server listening on pipe '{PipeName}' (Elevated: {Elevated}).", PipeName, IsProcessElevated());

        while (!cancellationToken.IsCancellationRequested)
        {
            NamedPipeServerStream? serverStream = null;
            try
            {
                var pipeSecurity = new PipeSecurity();
                
                // Grant FullControl to Administrators, SYSTEM, and Current User
                pipeSecurity.AddAccessRule(new PipeAccessRule(
                    new SecurityIdentifier(WellKnownSidType.BuiltinAdministratorsSid, null),
                    PipeAccessRights.FullControl,
                    AccessControlType.Allow));

                pipeSecurity.AddAccessRule(new PipeAccessRule(
                    new SecurityIdentifier(WellKnownSidType.LocalSystemSid, null),
                    PipeAccessRights.FullControl,
                    AccessControlType.Allow));

                try
                {
                    var currentUser = WindowsIdentity.GetCurrent().User;
                    if (currentUser != null)
                    {
                        pipeSecurity.AddAccessRule(new PipeAccessRule(
                            currentUser,
                            PipeAccessRights.FullControl,
                            AccessControlType.Allow));
                    }
                }
                catch { }

                // Grant ReadWrite + CreateNewInstance to Everyone (WorldSid)
                pipeSecurity.AddAccessRule(new PipeAccessRule(
                    new SecurityIdentifier(WellKnownSidType.WorldSid, null),
                    PipeAccessRights.ReadWrite | PipeAccessRights.CreateNewInstance,
                    AccessControlType.Allow));
                
                serverStream = NamedPipeServerStreamAcl.Create(
                    PipeName, 
                    PipeDirection.InOut, 
                    NamedPipeServerStream.MaxAllowedServerInstances, 
                    PipeTransmissionMode.Byte, 
                    PipeOptions.Asynchronous, 
                    0, 0, pipeSecurity,
                    HandleInheritability.None,
                    PipeAccessRights.ChangePermissions);

                // Apply Low Mandatory Integrity Level so unelevated (Medium Integrity) UI can connect to elevated Helper
                ApplyLowMandatoryIntegrity(serverStream, _logger);
                
                await serverStream.WaitForConnectionAsync(cancellationToken);

                // Handle the connection asynchronously so the next server instance is listening immediately
                var activeStream = serverStream;
                _ = Task.Run(async () =>
                {
                    using (activeStream)
                    {
                        await ProcessClientConnectionAsync(activeStream, cancellationToken);
                    }
                }, cancellationToken);
            }
            catch (OperationCanceledException)
            {
                serverStream?.Dispose();
                break;
            }
            catch (Exception ex)
            {
                serverStream?.Dispose();
                _logger.LogError(ex, "Error accepting IPC connection.");
                await Task.Delay(500, cancellationToken);
            }
        }
    }

    private async Task ProcessClientConnectionAsync(NamedPipeServerStream stream, CancellationToken cancellationToken)
    {
        _logger.LogInformation("[IPC Milestone] Client connected.");
        try
        {
            // Read length prefix (4 bytes)
            var lengthBytes = new byte[4];
            try
            {
                await stream.ReadExactlyAsync(lengthBytes, cancellationToken);
            }
            catch (EndOfStreamException)
            {
                _logger.LogDebug("[IPC Milestone] Client disconnected without sending data.");
                return;
            }

            var requestLength = BitConverter.ToInt32(lengthBytes, 0);
            if (requestLength <= 0 || requestLength > 10 * 1024 * 1024)
            {
                _logger.LogWarning("[IPC Milestone] Invalid request length received: {Length}", requestLength);
                await WriteResponseAsync<object>(stream, false, null, $"Invalid request length ({requestLength} bytes).", "INVALID_LENGTH", cancellationToken);
                return;
            }

            var requestBytes = new byte[requestLength];
            try
            {
                await stream.ReadExactlyAsync(requestBytes, cancellationToken);
            }
            catch (EndOfStreamException)
            {
                _logger.LogWarning("[IPC Milestone] Client disconnected before sending full request payload.");
                return;
            }

            var requestJson = Encoding.UTF8.GetString(requestBytes);
            IpcMessage? request;
            try
            {
                request = JsonSerializer.Deserialize<IpcMessage>(requestJson, _jsonOptions);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "[IPC Milestone] Failed to deserialize IPC message: {Json}", requestJson);
                await WriteResponseAsync<object>(stream, false, null, $"Invalid JSON request: {ex.Message}", "DESERIALIZATION_ERROR", cancellationToken);
                return;
            }

            if (request == null)
            {
                _logger.LogWarning("[IPC Milestone] IPC message deserialized to null.");
                await WriteResponseAsync<object>(stream, false, null, "IPC request was empty.", "EMPTY_REQUEST", cancellationToken);
                return;
            }

            _logger.LogInformation("[IPC Milestone] Processing Action='{Action}', PayloadBytes={Length}", request.Action, requestLength);
            await HandleRequestAsync(stream, request, cancellationToken);
        }
        catch (OperationCanceledException)
        {
            // Normal cancellation
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "[IPC Milestone] Error handling IPC request.");
            try
            {
                await WriteResponseAsync<object>(stream, false, null, $"Internal helper error: {ex.Message}", "INTERNAL_ERROR", cancellationToken);
            }
            catch { }
        }
    }

    private async Task HandleRequestAsync(NamedPipeServerStream stream, IpcMessage request, CancellationToken cancellationToken)
    {
        object? resultData = null;
        bool success = true;
        string? error = null;
        string? errorCode = null;

        try
        {
            switch (request.Action)
            {
                case "Start":
                    if (OnStartRequested == null)
                    {
                        throw new InvalidOperationException("Start requested but no handler is registered.");
                    }
                    if (string.IsNullOrWhiteSpace(request.Payload))
                    {
                        throw new ArgumentException("Start requested without payload.");
                    }

                    StartVpnRequest? startReq;
                    try
                    {
                        startReq = JsonSerializer.Deserialize<StartVpnRequest>(request.Payload, _jsonOptions);
                    }
                    catch (Exception ex)
                    {
                        throw new ArgumentException($"Failed to deserialize StartVpnRequest payload: {ex.Message}", ex);
                    }

                    if (startReq?.Config == null || string.IsNullOrWhiteSpace(startReq.Config.JsonConfig))
                    {
                        throw new ArgumentException("Start requested with empty or missing VPN configuration.");
                    }

                    resultData = await OnStartRequested(startReq);
                    break;

                case "Stop":
                    if (OnStopRequested != null)
                        resultData = await OnStopRequested();
                    else
                        resultData = true;
                    break;

                case "GetStatus":
                    if (OnStatusRequested != null)
                        resultData = OnStatusRequested();
                    else
                        resultData = HelperStatus.Stopped;
                    break;

                case "Ping":
                    resultData = true;
                    break;

                default:
                    success = false;
                    error = $"Unknown action '{request.Action}'.";
                    errorCode = "UNKNOWN_ACTION";
                    break;
            }
        }
        catch (Exception ex)
        {
            success = false;
            error = ex.Message;
            errorCode = "HANDLER_ERROR";
            _logger.LogError(ex, "[IPC Milestone] Handler error for action '{Action}'", request.Action);
        }

        await WriteResponseAsync(stream, success, resultData, error, errorCode, cancellationToken);
    }

    private async Task WriteResponseAsync<T>(NamedPipeServerStream stream, bool success, T? data, string? error, string? errorCode, CancellationToken cancellationToken)
    {
        try
        {
            var response = new IpcResponse<T>
            {
                Success = success,
                Data = data,
                ErrorMessage = error,
                ErrorCode = errorCode
            };

            var responseJson = JsonSerializer.Serialize(response, _jsonOptions);
            var responseBytes = Encoding.UTF8.GetBytes(responseJson);

            var lengthBytes = BitConverter.GetBytes(responseBytes.Length);
            await stream.WriteAsync(lengthBytes, cancellationToken);
            await stream.WriteAsync(responseBytes, cancellationToken);
            await stream.FlushAsync(cancellationToken);

            _logger.LogInformation("[IPC Milestone] Sent response: Success={Success}, Error={Error}, Length={Length}", success, error, responseBytes.Length);

            try
            {
                stream.WaitForPipeDrain();
            }
            catch (Exception ex)
            {
                _logger.LogDebug(ex, "WaitForPipeDrain completed or client closed pipe.");
            }

            // Wait for client to receive and close its stream before disposing server stream
            try
            {
                var ackBuffer = new byte[1];
                using var ackCts = new CancellationTokenSource(1500);
                await stream.ReadAsync(ackBuffer, ackCts.Token);
            }
            catch { }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "[IPC Milestone] Failed to write IPC response to client.");
        }
    }

    #region Windows Mandatory Integrity Control Interop
    private const int SE_KERNEL_OBJECT = 6;
    private const uint LABEL_SECURITY_INFORMATION = 0x00000010;

    [DllImport("advapi32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    private static extern bool ConvertStringSecurityDescriptorToSecurityDescriptorW(
        string StringSecurityDescriptor,
        uint StringSDRevision,
        out IntPtr SecurityDescriptor,
        out uint SecurityDescriptorSize);

    [DllImport("advapi32.dll", SetLastError = true)]
    private static extern uint SetSecurityInfo(
        SafeHandle handle,
        int ObjectType,
        uint SecurityInfo,
        IntPtr psidOwner,
        IntPtr psidGroup,
        IntPtr pDacl,
        IntPtr pSacl);

    [DllImport("advapi32.dll", SetLastError = true)]
    private static extern bool GetSecurityDescriptorSacl(
        IntPtr pSecurityDescriptor,
        out bool lpbSaclPresent,
        out IntPtr pSacl,
        out bool lpbSaclDefaulted);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern IntPtr LocalFree(IntPtr hMem);

    [DllImport("advapi32.dll", SetLastError = true)]
    private static extern bool OpenProcessToken(IntPtr ProcessHandle, uint DesiredAccess, out IntPtr TokenHandle);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool CloseHandle(IntPtr hObject);

    [DllImport("advapi32.dll", SetLastError = true)]
    private static extern bool GetTokenInformation(IntPtr TokenHandle, int TokenInformationClass, IntPtr TokenInformation, uint TokenInformationLength, out uint ReturnLength);

    private static void ApplyLowMandatoryIntegrity(NamedPipeServerStream stream, ILogger logger)
    {
        if (!OperatingSystem.IsWindows()) return;

        try
        {
            // S:(ML;;NW;;;LW) = Low Mandatory Level, No-Write-Up policy
            // Allows Medium Integrity (unelevated UI) to connect and write to High Integrity (elevated Helper) pipe
            string sddl = "S:(ML;;NW;;;LW)";
            if (ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl, 1, out IntPtr pSD, out _))
            {
                try
                {
                    if (GetSecurityDescriptorSacl(pSD, out bool saclPresent, out IntPtr pSacl, out _) && saclPresent && pSacl != IntPtr.Zero)
                    {
                        uint res = SetSecurityInfo(stream.SafePipeHandle, SE_KERNEL_OBJECT, LABEL_SECURITY_INFORMATION, IntPtr.Zero, IntPtr.Zero, IntPtr.Zero, pSacl);
                        if (res != 0)
                        {
                            logger.LogWarning("SetSecurityInfo for Low Mandatory Level returned code {Code}.", res);
                        }
                        else
                        {
                            logger.LogDebug("Successfully applied Low Mandatory Integrity to named pipe.");
                        }
                    }
                }
                finally
                {
                    LocalFree(pSD);
                }
            }
        }
        catch (Exception ex)
        {
            logger.LogWarning(ex, "Failed to apply Low Mandatory Integrity to pipe handle.");
        }
    }

    public static bool IsProcessElevated()
    {
        if (!OperatingSystem.IsWindows()) return false;
        try
        {
            using var proc = System.Diagnostics.Process.GetCurrentProcess();
            if (OpenProcessToken(proc.Handle, 0x0008 /* TOKEN_QUERY */, out IntPtr tokenHandle))
            {
                try
                {
                    int size = sizeof(int);
                    IntPtr pElevation = Marshal.AllocHGlobal(size);
                    try
                    {
                        if (GetTokenInformation(tokenHandle, 20 /* TokenElevation */, pElevation, (uint)size, out _))
                        {
                            return Marshal.ReadInt32(pElevation) != 0;
                        }
                    }
                    finally
                    {
                        Marshal.FreeHGlobal(pElevation);
                    }
                }
                finally
                {
                    CloseHandle(tokenHandle);
                }
            }
        }
        catch { }
        return false;
    }
    #endregion

    private class IpcMessage
    {
        public int ProtocolVersion { get; set; } = 1;
        public string Action { get; set; } = string.Empty;
        public string? Payload { get; set; }
    }

    private class IpcResponse<T>
    {
        public int ProtocolVersion { get; set; } = 1;
        public bool Success { get; set; }
        public T? Data { get; set; }
        public string? ErrorMessage { get; set; }
        public string? ErrorCode { get; set; }
    }
}

