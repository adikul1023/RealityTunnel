using System;

namespace OverREALITY.Helper;

public class ProcessExitedEventArgs : EventArgs
{
    public int ExitCode { get; }
    public TimeSpan Runtime { get; }
    public bool Unexpected { get; }

    public ProcessExitedEventArgs(int exitCode, TimeSpan runtime, bool unexpected)
    {
        ExitCode = exitCode;
        Runtime = runtime;
        Unexpected = unexpected;
    }
}
