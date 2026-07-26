using System;
using OverREALITY.Shared.Domain.Session;

namespace OverREALITY.Shared.Domain.Session;

public class SessionChangedEventArgs : EventArgs
{
    public Session? OldSession { get; }
    public Session? NewSession { get; }

    public SessionChangedEventArgs(Session? oldSession, Session? newSession)
    {
        OldSession = oldSession;
        NewSession = newSession;
    }
}
