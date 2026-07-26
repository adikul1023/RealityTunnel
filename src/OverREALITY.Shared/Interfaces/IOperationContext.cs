using System;

namespace OverREALITY.Shared.Interfaces;

public interface IOperationContext
{
    string? CurrentOperationId { get; }
    IDisposable BeginOperation(string operationName);
}
