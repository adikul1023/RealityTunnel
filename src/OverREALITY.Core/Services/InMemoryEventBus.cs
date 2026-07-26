using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using OverREALITY.Shared.Interfaces;

namespace OverREALITY.Core.Services;

public class InMemoryEventBus : IEventBus
{
    private readonly IServiceProvider _serviceProvider;
    private readonly ILogger<InMemoryEventBus> _logger;
    private readonly ConcurrentDictionary<Type, List<Type>> _handlers;
    private readonly SemaphoreSlim _semaphore;

    public InMemoryEventBus(IServiceProvider serviceProvider, ILogger<InMemoryEventBus> logger)
    {
        _serviceProvider = serviceProvider;
        _logger = logger;
        _handlers = new ConcurrentDictionary<Type, List<Type>>();
        _semaphore = new SemaphoreSlim(10, 10);
    }

    public async Task PublishAsync<T>(T @event, CancellationToken cancellationToken = default) where T : IIntegrationEvent
    {
        var eventType = typeof(T);
        _logger.LogInformation("Publishing event: {EventName} ({EventId})", eventType.Name, @event.Id);

        if (_handlers.TryGetValue(eventType, out var handlers))
        {
            var tasks = handlers.Select(async handlerType =>
            {
                await _semaphore.WaitAsync(cancellationToken);
                try
                {
                    var handler = _serviceProvider.GetService(handlerType);
                    if (handler != null)
                    {
                        if (handler is IIntegrationEventHandler<T> concreteHandler)
                        {
                            try
                            {
                                await concreteHandler.HandleAsync(@event, cancellationToken);
                            }
                            catch (Exception ex)
                            {
                                _logger.LogError(ex, "Error handling event {EventName} with {Handler}", eventType.Name, handlerType.Name);
                            }
                        }
                    }
                }
                finally
                {
                    _semaphore.Release();
                }
            });

            await Task.WhenAll(tasks);
        }
    }

    public void Subscribe<T, TH>()
        where T : IIntegrationEvent
        where TH : IIntegrationEventHandler<T>
    {
        var eventType = typeof(T);
        var handlerType = typeof(TH);

        if (!_handlers.ContainsKey(eventType))
        {
            _handlers.TryAdd(eventType, new List<Type>());
        }

        if (!_handlers[eventType].Contains(handlerType))
        {
            _handlers[eventType].Add(handlerType);
            _logger.LogInformation("Subscribed to event {EventName} with {HandlerName}", eventType.Name, handlerType.Name);
        }
    }

    public void Unsubscribe<T, TH>()
        where T : IIntegrationEvent
        where TH : IIntegrationEventHandler<T>
    {
        var eventType = typeof(T);
        var handlerType = typeof(TH);

        if (_handlers.ContainsKey(eventType) && _handlers[eventType].Contains(handlerType))
        {
            _handlers[eventType].Remove(handlerType);
            _logger.LogInformation("Unsubscribed from event {EventName} with {HandlerName}", eventType.Name, handlerType.Name);
        }
    }
}
