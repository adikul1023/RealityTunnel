namespace RealityTunnel.OperationsConsole.Shared
{
    public enum AccountStatus
    {
        Active,
        Suspended,
        Expired,
        Pending,
        Cancelled
    }

    public enum ServiceHealthState
    {
        Ok,
        Degraded,
        Error,
        Unknown
    }

    public enum ProvisioningStatus
    {
        Synced,
        Pending,
        Failed,
        Suspended,
        Terminated,
        Unknown
    }
}
