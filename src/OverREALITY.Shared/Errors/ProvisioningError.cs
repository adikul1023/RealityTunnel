using System;

namespace OverREALITY.Shared.Errors;

public class ProvisioningError
{
    public string Code { get; set; } = string.Empty;
    public string Message { get; set; } = string.Empty;
    public Exception? Exception { get; set; }
}
