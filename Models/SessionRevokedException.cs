using System;

namespace RealityTunnel.Models;

public class SessionRevokedException : Exception
{
    public SessionRevokedException()
        : base("The session has been revoked.")
    {
    }

    public SessionRevokedException(string message)
        : base(message)
    {
    }

    public SessionRevokedException(string message, Exception inner)
        : base(message, inner)
    {
    }
}
