using System;
using System.Threading;
using Microsoft.Extensions.Logging;
using OverREALITY.Shared.Interfaces;

namespace OverREALITY.Infrastructure.Services;

public class OperationContext : IOperationContext
{
    private static readonly AsyncLocal<string?> _currentOperationId = new();
    private readonly ILogger<OperationContext> _logger;

    public OperationContext(ILogger<OperationContext> logger)
    {
        _logger = logger;
    }

    public string? CurrentOperationId => _currentOperationId.Value;

    public IDisposable BeginOperation(string operationName)
    {
        var previousId = _currentOperationId.Value;
        var operationId = Guid.NewGuid().ToString("N");
        _currentOperationId.Value = operationId;

        _logger.LogInformation("Starting operation '{OperationName}' with ID '{OperationId}' (Parent: '{ParentId}')", operationName, operationId, previousId);

        return new OperationScope(operationName, operationId, previousId, _logger);
    }

    private class OperationScope : IDisposable
    {
        private readonly string _operationName;
        private readonly string _operationId;
        private readonly string? _previousId;
        private readonly ILogger _logger;

        public OperationScope(string operationName, string operationId, string? previousId, ILogger logger)
        {
            _operationName = operationName;
            _operationId = operationId;
            _previousId = previousId;
            _logger = logger;
        }

        public void Dispose()
        {
            _logger.LogInformation("Completed operation '{OperationName}' with ID '{OperationId}'", _operationName, _operationId);
            _currentOperationId.Value = _previousId;
        }
    }
}
