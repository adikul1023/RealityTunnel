using OverREALITY.Infrastructure.Services;
using OverREALITY.Shared.Domain.Session;
using Xunit;

namespace OverREALITY.Tests.Infrastructure;

public class SessionManagerTests
{
    [Fact]
    public void UpdateSession_FiresEvent()
    {
        var manager = new SessionManager();
        var eventFired = false;
        manager.SessionChanged += (sender, args) =>
        {
            eventFired = true;
            Assert.NotNull(args.NewSession);
            Assert.Equal("test_jwt", args.NewSession.JWT);
        };

        var session = new Session { JWT = "test_jwt" };
        manager.UpdateSession(session);

        Assert.True(eventFired);
        Assert.Equal(session, manager.CurrentSession);
    }
}
