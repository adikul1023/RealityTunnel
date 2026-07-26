using System;
using OverREALITY.Shared.Interfaces;

namespace OverREALITY.Shared.Events;

public class IntegrationEvent : IIntegrationEvent
{
    public Guid Id { get; } = Guid.NewGuid();
    public DateTime CreationDate { get; } = DateTime.UtcNow;
}

public class ConnectionEstablishedEvent : IntegrationEvent
{
}

public class ConnectionLostEvent : IntegrationEvent
{
}

public class HelperCrashedEvent : IntegrationEvent
{
    public int ExitCode { get; set; }
    public TimeSpan Runtime { get; set; }
}
