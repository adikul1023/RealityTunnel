using System.Collections.Generic;
using OverREALITY.Shared.Interfaces;

namespace OverREALITY.Infrastructure.Services;

public class FeatureManager : IFeatureManager
{
    private readonly Dictionary<string, bool> _features;

    public FeatureManager()
    {
        // Defaults could be loaded from settings or build configuration
        _features = new Dictionary<string, bool>
        {
            { "Feature.KillSwitch", true },
            { "Feature.Heartbeat", true },
            { "Feature.Telemetry", false },
            { "Feature.Updater", true },
            { "Feature.ExperimentalProtocols", false }
        };
    }

    public bool EnableKillSwitch => _features.GetValueOrDefault("Feature.KillSwitch");
    public bool EnableHeartbeat => _features.GetValueOrDefault("Feature.Heartbeat");
    public bool EnableTelemetry => _features.GetValueOrDefault("Feature.Telemetry");
    public bool EnableUpdater => _features.GetValueOrDefault("Feature.Updater");
    public bool EnableExperimentalProtocols => _features.GetValueOrDefault("Feature.ExperimentalProtocols");
}
