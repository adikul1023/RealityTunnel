using System;
using System.IO;
using System.Text.Json;
using OverREALITY.Shared.Interfaces;

namespace OverREALITY.Infrastructure.Services;

public class DomainResolver : IDomainResolver
{
    public DomainResolver()
    {
        // Decode base64 to hide domain strings from raw binaries
        ApiBaseUrl = System.Text.Encoding.UTF8.GetString(Convert.FromBase64String("aHR0cHM6Ly9hcGkucmV2aWV3Ym9vay5iaXo="));
        EdgeHost = System.Text.Encoding.UTF8.GetString(Convert.FromBase64String("ZWRnZS5yZXZpZXdib29rLmJpeg=="));
        DownloadBase = System.Text.Encoding.UTF8.GetString(Convert.FromBase64String("aHR0cHM6Ly9kbC5yZXZpZXdib29rLmJpeg=="));
    }

    public string ApiBaseUrl { get; }
    public string EdgeHost { get; }
    public string DownloadBase { get; }
}
