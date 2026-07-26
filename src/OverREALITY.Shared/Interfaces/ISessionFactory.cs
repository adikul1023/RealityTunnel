using OverREALITY.Shared.Domain.Session;

namespace OverREALITY.Shared.Interfaces;

public interface ISessionFactory
{
    Session Create(string jwt, string accountId);
}
