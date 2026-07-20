using System;
using System.IO;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using RealityTunnel.Models;

namespace RealityTunnel.Shared;

public static class IpcFraming
{
    private const int MaxMessageLength = 10 * 1024 * 1024; // 10 MB limit

    public static async Task<IpcMessage?> ReadMessageAsync(Stream stream, CancellationToken cancellationToken = default)
    {
        byte[] lengthBuffer = new byte[4];
        int totalRead = 0;
        while (totalRead < 4)
        {
            int bytesRead = await stream.ReadAsync(lengthBuffer.AsMemory(totalRead, 4 - totalRead), cancellationToken);
            if (bytesRead == 0)
            {
                if (totalRead == 0) return null; // Clean EOF
                throw new EndOfStreamException("Connection closed mid-header.");
            }
            totalRead += bytesRead;
        }

        int length = BitConverter.ToInt32(lengthBuffer, 0);
        if (length <= 0 || length > MaxMessageLength)
        {
            throw new InvalidOperationException($"Invalid IPC message length received: {length}");
        }

        byte[] payloadBuffer = new byte[length];
        totalRead = 0;
        while (totalRead < length)
        {
            int bytesRead = await stream.ReadAsync(payloadBuffer.AsMemory(totalRead, length - totalRead), cancellationToken);
            if (bytesRead == 0)
            {
                throw new EndOfStreamException("Connection closed mid-payload.");
            }
            totalRead += bytesRead;
        }

        return JsonSerializer.Deserialize<IpcMessage>(payloadBuffer);
    }

    public static async Task WriteMessageAsync(Stream stream, IpcMessage message, CancellationToken cancellationToken = default)
    {
        byte[] payloadBytes = JsonSerializer.SerializeToUtf8Bytes(message);
        byte[] lengthBytes = BitConverter.GetBytes(payloadBytes.Length);

        await stream.WriteAsync(lengthBytes.AsMemory(), cancellationToken);
        await stream.WriteAsync(payloadBytes.AsMemory(), cancellationToken);
        await stream.FlushAsync(cancellationToken);
    }
}
