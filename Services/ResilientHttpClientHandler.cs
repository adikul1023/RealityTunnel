using System;
using System.Net.Http;
using System.Net.Security;
using System.Security.Cryptography.X509Certificates;
using System.Threading;
using System.Threading.Tasks;

namespace RealityTunnel.Services;

public class ResilientHttpClientHandler : DelegatingHandler
{
    private const int MaxRetries = 3;
    // Set to true once the real SPKI pin is available
    private const bool EnablePinning = false;
    private const string ExpectedSpkiPin = null; // Set to actual SHA256 string when enabled

    public ResilientHttpClientHandler(HttpMessageHandler innerHandler) : base(innerHandler)
    {
        if (innerHandler is HttpClientHandler clientHandler)
        {
            clientHandler.ServerCertificateCustomValidationCallback = ValidateServerCertificate;
        }
    }

    private bool ValidateServerCertificate(HttpRequestMessage request, X509Certificate2? cert, X509Chain? chain, SslPolicyErrors errors)
    {
        if (errors != SslPolicyErrors.None && errors != SslPolicyErrors.RemoteCertificateNameMismatch)
        {
            return false; // Real TLS errors fail fast
        }

        if (EnablePinning && cert != null && ExpectedSpkiPin != null && request.RequestUri?.Host == "api.stealthy.co.in")
        {
            // Compute SPKI hash (simulated logic for .NET 8)
            var spki = Convert.ToBase64String(cert.GetPublicKey());
            return $"sha256/{spki}" == ExpectedSpkiPin;
        }
        
        return true;
    }

    protected override async Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
    {
        int retries = 0;
        while (true)
        {
            try
            {
                var response = await base.SendAsync(request, cancellationToken);
                
                int statusCode = (int)response.StatusCode;
                
                if (statusCode >= 500 && statusCode <= 599)
                {
                    if (retries >= MaxRetries) return response;
                    await Task.Delay(TimeSpan.FromSeconds(Math.Pow(2, retries)), cancellationToken);
                    retries++;
                    continue;
                }
                
                if (statusCode == 429)
                {
                    if (retries >= MaxRetries) return response;
                    var retryAfter = response.Headers.RetryAfter?.Delta ?? TimeSpan.FromSeconds(2);
                    await Task.Delay(retryAfter, cancellationToken);
                    retries++;
                    continue;
                }
                
                // 400, 401, 403, 404, etc -> fail fast
                return response;
            }
            catch (HttpRequestException)
            {
                // Network failure or timeout
                if (retries >= 2) throw; // Timeout retries max 2
                await Task.Delay(TimeSpan.FromSeconds(1), cancellationToken);
                retries++;
            }
            catch (TaskCanceledException)
            {
                // Timeout
                if (retries >= 2) throw;
                await Task.Delay(TimeSpan.FromSeconds(1), cancellationToken);
                retries++;
            }
        }
    }
}
