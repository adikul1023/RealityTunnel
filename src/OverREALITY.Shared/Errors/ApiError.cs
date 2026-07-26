using System;

namespace OverREALITY.Shared.Errors;

public class ApiError
{
    public string Code { get; set; } = string.Empty;
    public string Message { get; set; } = string.Empty;
    public int StatusCode { get; set; }
    public bool Retryable { get; set; }
    public Exception? Exception { get; set; }
}
