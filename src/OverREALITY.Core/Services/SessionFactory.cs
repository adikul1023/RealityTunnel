using OverREALITY.Shared.Domain.Session;
using OverREALITY.Shared.Interfaces;

namespace OverREALITY.Core.Services;

public class SessionFactory : ISessionFactory
{
    public Session Create(string jwt, string accountId)
    {
        var session = new Session { JWT = jwt };
        session.User.AccountId = accountId;
        return session;
    }
}
