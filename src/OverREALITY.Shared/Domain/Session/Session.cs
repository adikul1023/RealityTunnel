using System;
using OverREALITY.Shared.Domain.User;
using OverREALITY.Shared.Api.Device;
using OverREALITY.Shared.Api.Configuration;

namespace OverREALITY.Shared.Domain.Session;

public class Session
{
    public UserProfile User { get; set; } = new();
    public SubscriptionInfo Subscription { get; set; } = new();
    public DeviceInfo Device { get; set; } = new();
    public string JWT { get; set; } = string.Empty;
    public ServerProfileDto? CurrentServer { get; set; }
    public DateTime? ConnectedSince { get; set; }
    public long BytesUploaded { get; set; }
    public long BytesDownloaded { get; set; }
}
