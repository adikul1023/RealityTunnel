using System;
using OverREALITY.Shared.Domain.Session;

namespace OverREALITY.Shared.Interfaces;

public interface ISessionManager
{
    event EventHandler<SessionChangedEventArgs>? SessionChanged;
    
    Session? CurrentSession { get; }
    void UpdateSession(Session session);
    void ClearSession();
}
