using System;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging.Abstractions;
using OverREALITY.Infrastructure.Services;
using Xunit;

namespace OverREALITY.Tests.Infrastructure;

public class SecureStorageTests
{
    [Fact]
    public async Task SaveAndGet_WorksCorrectly()
    {
        var logger = new NullLogger<SecureStorageService>();
        var service = new SecureStorageService(logger);
        var key = $"TestKey_{Guid.NewGuid()}";
        var value = "TestSecretValue";

        await service.SaveSecureAsync(key, value);
        var retrieved = await service.GetSecureAsync(key);

        Assert.Equal(value, retrieved);

        await service.DeleteSecureAsync(key);
        var afterDelete = await service.GetSecureAsync(key);
        Assert.Null(afterDelete);
    }
}
