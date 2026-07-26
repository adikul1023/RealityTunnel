namespace OverREALITY.Shared.Api;

public enum ConnectionState
{
    Disconnected,
    Authenticating,
    Provisioning,
    StartingHelper,
    Connecting,
    Connected,
    Reconnecting,
    Disconnecting,
    Failed
}
