using System;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging.Abstractions;
using OverREALITY.Core.Services;
using OverREALITY.Shared.Events;
using OverREALITY.Shared.Interfaces;
using Xunit;

namespace OverREALITY.Tests.Core;

public class TestEvent : IntegrationEvent { }

public class TestEventHandler : IIntegrationEventHandler<TestEvent>
{
    public bool Handled { get; private set; }
    
    public Task HandleAsync(TestEvent @event, CancellationToken cancellationToken = default)
    {
        Handled = true;
        return Task.CompletedTask;
    }
}

public class InMemoryEventBusTests
{
    [Fact]
    public async Task PublishAsync_InvokesHandler_WhenSubscribed()
    {
        var services = new ServiceCollection();
        services.AddSingleton<TestEventHandler>();
        var provider = services.BuildServiceProvider();

        var bus = new InMemoryEventBus(provider, NullLogger<InMemoryEventBus>.Instance);
        
        bus.Subscribe<TestEvent, TestEventHandler>();

        var testEvent = new TestEvent();
        await bus.PublishAsync(testEvent);

        var handler = provider.GetRequiredService<TestEventHandler>();
        Assert.True(handler.Handled);
    }
}
