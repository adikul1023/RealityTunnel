using System;

namespace OverREALITY.Shared.Errors;

public class AuthenticationError
{
    public string Code { get; set; } = string.Empty;
    public string Message { get; set; } = string.Empty;
    public int StatusCode { get; set; }
    public bool Retryable { get; set; }
    public bool Requires2Fa { get; set; }
    public Exception? Exception { get; set; }
}
