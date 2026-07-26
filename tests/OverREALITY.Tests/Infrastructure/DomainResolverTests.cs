using System;
using System.IO;
using System.Text.Json;
using OverREALITY.Infrastructure.Services;
using Xunit;

namespace OverREALITY.Tests.Infrastructure;

public class DomainResolverTests : IDisposable
{
    private readonly string _envPath;

    public DomainResolverTests()
    {
        _envPath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "environment.json");
    }

    [Fact]
    public void Constructor_Throws_WhenEnvironmentMissing()
    {
        if (File.Exists(_envPath)) File.Delete(_envPath);
        Assert.Throws<InvalidOperationException>(() => new DomainResolver());
    }

    [Fact]
    public void Properties_ReturnValuesFromEnvironmentFile()
    {
        var config = new { ApiBaseUrl = "https://custom.api.stealthy.co.in", EdgeHost = "custom.edge.co.in", DownloadBase = "https://dl.custom.co.in" };
        File.WriteAllText(_envPath, JsonSerializer.Serialize(config));

        var resolver = new DomainResolver();

        Assert.Equal("https://custom.api.stealthy.co.in", resolver.ApiBaseUrl);
        Assert.Equal("custom.edge.co.in", resolver.EdgeHost);
        Assert.Equal("https://dl.custom.co.in", resolver.DownloadBase);
    }

    public void Dispose()
    {
        if (File.Exists(_envPath)) File.Delete(_envPath);
    }
}
