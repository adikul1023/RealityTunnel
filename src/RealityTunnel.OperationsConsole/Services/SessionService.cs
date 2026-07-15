using System;
using System.Windows.Threading;
using RealityTunnel.OperationsConsole.Shared;

namespace RealityTunnel.OperationsConsole.Services
{
    public interface ISessionService
    {
        bool IsAuthenticated { get; }
        string AccessToken { get; }
        string CurrentUsername { get; }
        string CurrentRole { get; }
        string ServerBaseUrl { get; set; }

        event EventHandler? SessionExpired;

        void SetSession(string token, string username, string role);
        void RegisterActivity();
        void ClearSession();
    }

    /// <summary>
    /// Volatile RAM-only authentication and session manager.
    /// Strictly guarantees JWT is never written to disk, registry, settings, DPAPI, clipboard, or logs.
    /// Enforces a 10-minute inactivity auto-logout policy.
    /// </summary>
    public class SessionService : ISessionService
    {
        private volatile string _accessToken = string.Empty;
        private volatile string _currentUsername = string.Empty;
        private volatile string _currentRole = string.Empty;
        private string _serverBaseUrl = "https://api.stealthy.co.in";
        private readonly DispatcherTimer _inactivityTimer;
        private readonly TimeSpan _timeoutDuration = TimeSpan.FromMinutes(10);

        public event EventHandler? SessionExpired;

        public bool IsAuthenticated => !string.IsNullOrEmpty(_accessToken);
        public string AccessToken => _accessToken;
        public string CurrentUsername => _currentUsername;
        public string CurrentRole => _currentRole;

        public string ServerBaseUrl
        {
            get => _serverBaseUrl;
            set => _serverBaseUrl = value?.TrimEnd('/') ?? "https://api.stealthy.co.in";
        }

        public SessionService()
        {
            _inactivityTimer = new DispatcherTimer
            {
                Interval = TimeSpan.FromSeconds(30) // Check periodically
            };
            _inactivityTimer.Tick += OnTimerTick;
        }

        private DateTime _lastActivity = DateTime.UtcNow;

        private void OnTimerTick(object? sender, EventArgs e)
        {
            if (!IsAuthenticated)
            {
                _inactivityTimer.Stop();
                return;
            }

            if (DateTime.UtcNow - _lastActivity >= _timeoutDuration)
            {
                ClearSession();
                SessionExpired?.Invoke(this, EventArgs.Empty);
            }
        }

        public void SetSession(string token, string username, string role)
        {
            _accessToken = token;
            _currentUsername = username;
            _currentRole = role;
            _lastActivity = DateTime.UtcNow;
            _inactivityTimer.Start();
        }

        public void RegisterActivity()
        {
            if (IsAuthenticated)
            {
                _lastActivity = DateTime.UtcNow;
            }
        }

        public void ClearSession()
        {
            _inactivityTimer.Stop();
            _accessToken = string.Empty;
            _currentUsername = string.Empty;
            _currentRole = string.Empty;
        }
    }
}
