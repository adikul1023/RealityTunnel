namespace OverREALITY.Shared.Interfaces;

public interface IFeatureManager
{
    bool EnableKillSwitch { get; }
    bool EnableHeartbeat { get; }
    bool EnableTelemetry { get; }
    bool EnableUpdater { get; }
    bool EnableExperimentalProtocols { get; }
}
