using System;
using OverREALITY.Shared.Interfaces;
using OverREALITY.Shared.Domain.Session;

namespace OverREALITY.Infrastructure.Services;

public class SessionManager : ISessionManager
{
    public event EventHandler<SessionChangedEventArgs>? SessionChanged;

    private Session? _currentSession;

    public Session? CurrentSession => _currentSession;

    public void UpdateSession(Session session)
    {
        var oldSession = _currentSession;
        _currentSession = session;
        SessionChanged?.Invoke(this, new SessionChangedEventArgs(oldSession, _currentSession));
    }

    public void ClearSession()
    {
        if (_currentSession != null)
        {
            var oldSession = _currentSession;
            _currentSession = null;
            SessionChanged?.Invoke(this, new SessionChangedEventArgs(oldSession, null));
        }
    }
}
