using System;

namespace OverREALITY.Shared.Errors;

public class HelperError
{
    public string Message { get; set; } = string.Empty;
    public string? Code { get; set; }
    public Exception? Exception { get; set; }
}
