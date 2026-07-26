using System;
using System.IO;
using System.Text.Json;
using OverREALITY.Shared.Interfaces;

namespace OverREALITY.Infrastructure.Services;

public class DomainResolver : IDomainResolver
{
    private class EnvConfig
    {
        public string ApiBaseUrl { get; set; } = string.Empty;
        public string EdgeHost { get; set; } = string.Empty;
        public string DownloadBase { get; set; } = string.Empty;
    }

    private readonly EnvConfig _config;

    public DomainResolver()
    {
        var envPath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "environment.json");
        if (!File.Exists(envPath))
        {
            throw new InvalidOperationException($"Environment configuration missing at {envPath}");
        }

        var json = File.ReadAllText(envPath);
        var parsed = JsonSerializer.Deserialize<EnvConfig>(json, new JsonSerializerOptions { PropertyNameCaseInsensitive = true });
        
        if (parsed == null || string.IsNullOrWhiteSpace(parsed.ApiBaseUrl))
        {
            throw new InvalidOperationException("Invalid environment configuration format.");
        }

        _config = parsed;
    }

    public string ApiBaseUrl => _config.ApiBaseUrl;
    public string EdgeHost => _config.EdgeHost;
    public string DownloadBase => _config.DownloadBase;
}
