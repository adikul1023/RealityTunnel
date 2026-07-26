using System;
using System.Threading;
using System.Threading.Tasks;

namespace OverREALITY.Shared.Interfaces;

public interface IIntegrationEvent
{
    Guid Id { get; }
    DateTime CreationDate { get; }
}

public interface IEventBus
{
    Task PublishAsync<T>(T @event, CancellationToken cancellationToken = default) where T : IIntegrationEvent;
    void Subscribe<T, TH>()
        where T : IIntegrationEvent
        where TH : IIntegrationEventHandler<T>;
    void Unsubscribe<T, TH>()
        where T : IIntegrationEvent
        where TH : IIntegrationEventHandler<T>;
}

public interface IIntegrationEventHandler<in TIntegrationEvent> : IIntegrationEventHandler
    where TIntegrationEvent : IIntegrationEvent
{
    Task HandleAsync(TIntegrationEvent @event, CancellationToken cancellationToken = default);
}

public interface IIntegrationEventHandler
{
}
