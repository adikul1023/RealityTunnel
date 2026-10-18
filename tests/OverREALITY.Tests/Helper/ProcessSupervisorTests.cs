using System;
using System.IO;
using System.Reflection;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging.Abstractions;
using OverREALITY.Helper;
using OverREALITY.Shared.Api.VpnRuntime;
using Xunit;

namespace OverREALITY.Tests.Helper;

public class ProcessSupervisorTests
{
    [Fact]
    public void StateMachine_ValidTransitions_Succeed()
    {
        var sm = new HelperStateMachine(NullLogger<HelperStateMachine>.Instance);
        Assert.Equal(HelperStatus.Stopped, sm.CurrentStatus);

        sm.TransitionTo(HelperStatus.Starting);
        Assert.Equal(HelperStatus.Starting, sm.CurrentStatus);

        sm.TransitionTo(HelperStatus.Running);
        Assert.Equal(HelperStatus.Running, sm.CurrentStatus);

        sm.TransitionTo(HelperStatus.Stopping);
        Assert.Equal(HelperStatus.Stopping, sm.CurrentStatus);

        sm.TransitionTo(HelperStatus.Stopped);
        Assert.Equal(HelperStatus.Stopped, sm.CurrentStatus);
    }

    [Fact]
    public void StateMachine_InvalidTransition_ThrowsAndPreservesState()
    {
        var sm = new HelperStateMachine(NullLogger<HelperStateMachine>.Instance);
        Assert.Equal(HelperStatus.Stopped, sm.CurrentStatus);

        // Cannot jump directly from Stopped to Running
        Assert.Throws<InvalidOperationException>(() => sm.TransitionTo(HelperStatus.Running));
        Assert.Equal(HelperStatus.Stopped, sm.CurrentStatus);

        // Cannot jump directly from Stopped to Crashed
        Assert.False(sm.TryTransitionTo(HelperStatus.Crashed, out var prev));
        Assert.Equal(HelperStatus.Stopped, prev);
        Assert.Equal(HelperStatus.Stopped, sm.CurrentStatus);
    }

    [Fact]
    public void StateMachine_IdempotentTransition_Succeeds()
    {
        var sm = new HelperStateMachine(NullLogger<HelperStateMachine>.Instance);
        Assert.True(sm.TryTransitionTo(HelperStatus.Stopped, out _));
        Assert.Equal(HelperStatus.Stopped, sm.CurrentStatus);
    }

    [Fact]
    public async Task ProcessSupervisor_ConcurrentStartupFailureAndProcessExit_IsRaceSafe()
    {
        for (int iter = 0; iter < 50; iter++)
        {
            var sm = new HelperStateMachine(NullLogger<HelperStateMachine>.Instance);
            var pm = new SingboxProcessManager(NullLogger<SingboxProcessManager>.Instance);
            using var supervisor = new ProcessSupervisor(pm, sm, NullLogger<ProcessSupervisor>.Instance);

            // Set state to Starting as would happen when StartInternalAsync begins
            sm.TransitionTo(HelperStatus.Starting);

            // Concurrently:
            // Path A: Startup failure detects exit and transitions Starting -> Stopped
            // Path B: ProcessExited event fires and calls OnProcessExited
            var barrier = new Barrier(2);

            var taskA = Task.Run(() =>
            {
                barrier.SignalAndWait();
                // Simulate StartInternalAsync catch block
                sm.TryTransitionTo(HelperStatus.Stopped, out _);
            });

            var taskB = Task.Run(() =>
            {
                barrier.SignalAndWait();
                // Trigger OnProcessExited via reflection or direct invocation of event
                var eventMethod = typeof(SingboxProcessManager).GetField("ProcessExited", BindingFlags.Instance | BindingFlags.NonPublic);
                var handler = eventMethod?.GetValue(pm) as EventHandler<ProcessExitedEventArgs>;
                handler?.Invoke(pm, new ProcessExitedEventArgs(1, TimeSpan.FromMilliseconds(400), false));
            });

            await Task.WhenAll(taskA, taskB);

            // After race resolves, state MUST be Stopped, never corrupt or crashed
            Assert.Equal(HelperStatus.Stopped, sm.CurrentStatus);
        }
    }

    [Fact]
    public void ProcessSupervisor_ProcessExitWhileStopped_IsIgnoredSafely()
    {
        var sm = new HelperStateMachine(NullLogger<HelperStateMachine>.Instance);
        var pm = new SingboxProcessManager(NullLogger<SingboxProcessManager>.Instance);
        using var supervisor = new ProcessSupervisor(pm, sm, NullLogger<ProcessSupervisor>.Instance);

        Assert.Equal(HelperStatus.Stopped, sm.CurrentStatus);

        // Fire process exit when supervisor is in Stopped state
        var eventMethod = typeof(SingboxProcessManager).GetField("ProcessExited", BindingFlags.Instance | BindingFlags.NonPublic);
        var handler = eventMethod?.GetValue(pm) as EventHandler<ProcessExitedEventArgs>;
        
        // Multiple rapid exit events
        handler?.Invoke(pm, new ProcessExitedEventArgs(1, TimeSpan.FromSeconds(1), false));
        handler?.Invoke(pm, new ProcessExitedEventArgs(0, TimeSpan.FromSeconds(2), false));

        Assert.Equal(HelperStatus.Stopped, sm.CurrentStatus);
    }

    [Fact]
    public void ProcessSupervisor_ProcessExitWhileRunning_TransitionsToCrashed()
    {
        var sm = new HelperStateMachine(NullLogger<HelperStateMachine>.Instance);
        var pm = new SingboxProcessManager(NullLogger<SingboxProcessManager>.Instance);
        using var supervisor = new ProcessSupervisor(pm, sm, NullLogger<ProcessSupervisor>.Instance);

        sm.TransitionTo(HelperStatus.Starting);
        sm.TransitionTo(HelperStatus.Running);

        var eventMethod = typeof(SingboxProcessManager).GetField("ProcessExited", BindingFlags.Instance | BindingFlags.NonPublic);
        var handler = eventMethod?.GetValue(pm) as EventHandler<ProcessExitedEventArgs>;
        handler?.Invoke(pm, new ProcessExitedEventArgs(1, TimeSpan.FromSeconds(5), true));

        // State machine should transition from Running to Crashed, then to Restarting
        var status = sm.CurrentStatus;
        Assert.True(status == HelperStatus.Crashed || status == HelperStatus.Restarting);
    }
}