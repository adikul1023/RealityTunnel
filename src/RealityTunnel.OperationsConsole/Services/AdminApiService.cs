using System;
using System.Net;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using RealityTunnel.OperationsConsole.Shared;

namespace RealityTunnel.OperationsConsole.Services
{
    public interface IAdminApiService
    {
        Task<ApiResult<T>> GetAsync<T>(string route, CancellationToken cancellationToken = default);
        Task<ApiResult<T>> PostAsync<T, TBody>(string route, TBody body, CancellationToken cancellationToken = default);
        Task<ApiResult<T>> PostAsync<T>(string route, CancellationToken cancellationToken = default);
        Task<ApiResult<T>> PatchAsync<T, TBody>(string route, TBody body, CancellationToken cancellationToken = default);
        Task<ApiResult<T>> PatchAsync<T>(string route, CancellationToken cancellationToken = default);
        Task<ApiResult<T>> DeleteAsync<T>(string route, CancellationToken cancellationToken = default);
    }

    public class AdminApiService : IAdminApiService
    {
        private readonly IHttpClientFactory _httpClientFactory;
        private readonly ISessionService _sessionService;
        private readonly IDialogService _dialogService;
        private readonly INavigationService _navigationService;
        private readonly JsonSerializerOptions _jsonOptions;

        public AdminApiService(
            IHttpClientFactory httpClientFactory,
            ISessionService sessionService,
            IDialogService dialogService,
            INavigationService navigationService)
        {
            _httpClientFactory = httpClientFactory;
            _sessionService = sessionService;
            _dialogService = dialogService;
            _navigationService = navigationService;
            _jsonOptions = new JsonSerializerOptions
            {
                PropertyNameCaseInsensitive = true
            };
        }

        private HttpClient CreateClient()
        {
            var client = _httpClientFactory.CreateClient("AdminApiClient");
            client.BaseAddress = new Uri(_sessionService.ServerBaseUrl);
            client.Timeout = TimeSpan.FromSeconds(15);

            if (_sessionService.IsAuthenticated)
            {
                _sessionService.RegisterActivity();
                client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", _sessionService.AccessToken);
            }

            return client;
        }

        public async Task<ApiResult<T>> GetAsync<T>(string route, CancellationToken cancellationToken = default) =>
            await ExecuteRequestAsync<T>(() => CreateClient().GetAsync(route, cancellationToken), route, cancellationToken);

        public async Task<ApiResult<T>> PostAsync<T, TBody>(string route, TBody body, CancellationToken cancellationToken = default) =>
            await ExecuteRequestAsync<T>(() => CreateClient().PostAsJsonAsync(route, body, _jsonOptions, cancellationToken), route, cancellationToken);

        public async Task<ApiResult<T>> PostAsync<T>(string route, CancellationToken cancellationToken = default) =>
            await ExecuteRequestAsync<T>(() => CreateClient().PostAsync(route, null, cancellationToken), route, cancellationToken);

        public async Task<ApiResult<T>> PatchAsync<T, TBody>(string route, TBody body, CancellationToken cancellationToken = default) =>
            await ExecuteRequestAsync<T>(() => CreateClient().PatchAsJsonAsync(route, body, _jsonOptions, cancellationToken), route, cancellationToken);

        public async Task<ApiResult<T>> PatchAsync<T>(string route, CancellationToken cancellationToken = default) =>
            await ExecuteRequestAsync<T>(() => CreateClient().PatchAsync(route, null, cancellationToken), route, cancellationToken);

        public async Task<ApiResult<T>> DeleteAsync<T>(string route, CancellationToken cancellationToken = default) =>
            await ExecuteRequestAsync<T>(() => CreateClient().DeleteAsync(route, cancellationToken), route, cancellationToken);

        private async Task<ApiResult<T>> ExecuteRequestAsync<T>(Func<Task<HttpResponseMessage>> requestFunc, string route, CancellationToken cancellationToken)
        {
            int attempt = 0;
            const int maxAttempts = 2;

            while (attempt < maxAttempts)
            {
                attempt++;
                try
                {
                    var response = await requestFunc();

                    if (response.IsSuccessStatusCode)
                    {
                        if (response.StatusCode == HttpStatusCode.NoContent)
                        {
                            return ApiResult<T>.Success(default!, (int)response.StatusCode);
                        }

                        var data = await response.Content.ReadFromJsonAsync<T>(_jsonOptions, cancellationToken);
                        return ApiResult<T>.Success(data!, (int)response.StatusCode);
                    }

                    // Handle 401 Unauthorized
                    if (response.StatusCode == HttpStatusCode.Unauthorized)
                    {
                        _sessionService.ClearSession();
                        _navigationService.ShowLoginWindow();
                        return ApiResult<T>.Failure("Session expired or unauthorized. Returning to login.", 401, isUnauthorized: true);
                    }

                    // Handle 403 Forbidden
                    if (response.StatusCode == HttpStatusCode.Forbidden)
                    {
                        await _dialogService.ShowErrorAsync("Permission Denied", "You do not have the required super-admin permissions to perform this action.");
                        return ApiResult<T>.Failure("Permission denied.", 403, isForbidden: true);
                    }

                    // Handle 5xx Server Errors (Retry once)
                    if ((int)response.StatusCode >= 500)
                    {
                        if (attempt < maxAttempts)
                        {
                            await Task.Delay(1000, cancellationToken);
                            continue;
                        }

                        string errText = await response.Content.ReadAsStringAsync(cancellationToken);
                        string userMsg = $"Server encountered an error (HTTP {(int)response.StatusCode}): {errText}";
                        await _dialogService.ShowErrorAsync("Backend Service Error", userMsg);
                        return ApiResult<T>.Failure(userMsg, (int)response.StatusCode);
                    }

                    // Handle 4xx or other client errors
                    string clientErrText = await response.Content.ReadAsStringAsync(cancellationToken);
                    string errMsg = ExtractDetailMessage(clientErrText, (int)response.StatusCode);
                    return ApiResult<T>.Failure(errMsg, (int)response.StatusCode);
                }
                catch (TaskCanceledException)
                {
                    if (attempt >= maxAttempts)
                    {
                        string msg = "Network request timed out while contacting the backend server.";
                        await _dialogService.ShowErrorAsync("Connection Timeout", msg);
                        return ApiResult<T>.Failure(msg, 408);
                    }
                    await Task.Delay(1000, cancellationToken);
                }
                catch (HttpRequestException ex)
                {
                    if (attempt >= maxAttempts)
                    {
                        string msg = $"Unable to connect to backend server ({_sessionService.ServerBaseUrl}). Please verify network connection or server status.\nDetails: {ex.Message}";
                        await _dialogService.ShowErrorAsync("Offline / Network Error", msg);
                        return ApiResult<T>.Failure(msg, 503);
                    }
                    await Task.Delay(1000, cancellationToken);
                }
                catch (Exception ex)
                {
                    return ApiResult<T>.Failure($"Unexpected error: {ex.Message}", 500);
                }
            }

            return ApiResult<T>.Failure("Request failed after retries.", 500);
        }

        private static string ExtractDetailMessage(string rawJsonOrText, int statusCode)
        {
            try
            {
                using var doc = JsonDocument.Parse(rawJsonOrText);
                if (doc.RootElement.TryGetProperty("detail", out var detailProp))
                {
                    if (detailProp.ValueKind == JsonValueKind.String)
                        return detailProp.GetString() ?? rawJsonOrText;
                    if (detailProp.ValueKind == JsonValueKind.Array || detailProp.ValueKind == JsonValueKind.Object)
                        return detailProp.GetRawText();
                }
            }
            catch
            {
                // Fallback if not valid JSON
            }
            return string.IsNullOrWhiteSpace(rawJsonOrText) ? $"HTTP {statusCode} Error" : rawJsonOrText;
        }
    }
}
