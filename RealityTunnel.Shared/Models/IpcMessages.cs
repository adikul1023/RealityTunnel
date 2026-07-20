using System;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace RealityTunnel.Models;

public static class IpcMessageTypes
{
    public const string Hello = "Hello";
    public const string Connect = "Connect";
    public const string Disconnect = "Disconnect";
    public const string GetStatus = "GetStatus";
    public const string Ping = "Ping";
    public const string Ack = "Ack";
    public const string Error = "Error";
    public const string StatusChanged = "StatusChanged";
    public const string GetHelperLog = "GetHelperLog";
}

public static class IpcErrorCodes
{
    public const string VersionMismatch = "VersionMismatch";
    public const string Unauthorized = "Unauthorized";
    public const string InvalidSequence = "InvalidSequence";
    public const string HandshakeRequired = "HandshakeRequired";
    public const string OperationFailed = "OperationFailed";
}

public class IpcMessage
{
    [JsonPropertyName("protocolVersion")]
    public int ProtocolVersion { get; set; } = 1;

    [JsonPropertyName("requestId")]
    public string RequestId { get; set; } = Guid.NewGuid().ToString();

    [JsonPropertyName("sessionToken")]
    public string? SessionToken { get; set; }

    [JsonPropertyName("sequence")]
    public long Sequence { get; set; }

    [JsonPropertyName("issuedAtUtc")]
    public DateTimeOffset IssuedAtUtc { get; set; } = DateTimeOffset.UtcNow;

    [JsonPropertyName("type")]
    public string Type { get; set; } = "";

    [JsonPropertyName("payload")]
    public JsonElement? Payload { get; set; }

    public static IpcMessage Create<T>(string type, T payloadObject, string? sessionToken = null, long sequence = 0, string? requestId = null)
    {
        return new IpcMessage
        {
            Type = type,
            SessionToken = sessionToken,
            Sequence = sequence,
            RequestId = requestId ?? Guid.NewGuid().ToString(),
            Payload = JsonSerializer.SerializeToElement(payloadObject)
        };
    }

    public static IpcMessage CreateEmpty(string type, string? sessionToken = null, long sequence = 0, string? requestId = null)
    {
        return new IpcMessage
        {
            Type = type,
            SessionToken = sessionToken,
            Sequence = sequence,
            RequestId = requestId ?? Guid.NewGuid().ToString(),
            Payload = null
        };
    }

    public T? GetPayload<T>()
    {
        if (!Payload.HasValue)
            return default;
        return JsonSerializer.Deserialize<T>(Payload.Value.GetRawText());
    }
}

public class HelloRequest
{
    [JsonPropertyName("clientPid")]
    public int ClientPid { get; set; }
}

public class HelloResponse
{
    [JsonPropertyName("sessionToken")]
    public string SessionToken { get; set; } = "";

    [JsonPropertyName("serviceVersion")]
    public string ServiceVersion { get; set; } = "1.0.0";
}

public class GetStatusResponse
{
    [JsonPropertyName("desiredState")]
    public string DesiredState { get; set; } = "Disconnected";

    [JsonPropertyName("actualState")]
    public string ActualState { get; set; } = "Disconnected";

    [JsonPropertyName("connectedSince")]
    public DateTimeOffset? ConnectedSince { get; set; }

    [JsonPropertyName("lastError")]
    public string? LastError { get; set; }
}

public class ErrorResponse
{
    [JsonPropertyName("errorCode")]
    public string ErrorCode { get; set; } = "";

    [JsonPropertyName("message")]
    public string Message { get; set; } = "";
}

public class StatusChangedNotification
{
    [JsonPropertyName("desiredState")]
    public string DesiredState { get; set; } = "";

    [JsonPropertyName("actualState")]
    public string ActualState { get; set; } = "";

    [JsonPropertyName("error")]
    public string? Error { get; set; }
}
