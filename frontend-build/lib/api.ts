/**
 * lib/api.ts — Centralized Oracle Billing API Client (Phase 9.1)
 *
 * Responsibilities:
 * - Single entry point for all API communication with api.stealthy.co.in
 * - Authorization Bearer token attachment
 * - Automatic JWT refresh and single-retry rotation on 401
 * - Replay detection handling (destroys session immediately on replay detection)
 * - Request timeouts via AbortController
 * - Structured error handling (ApiError)
 *
 * Rule: Never store Master Token in storage. Never communicate with edge.stealthy.co.in, Contabo, Xray, or PostgreSQL directly.
 */

import { config } from './config';

// ─── Session Storage & Types ─────────────────────────────────────────────────

export interface AuthSession {
  accessToken: string;
  refreshToken: string;
  expiresAt: number; // Unix timestamp in ms
  accountId: string;
}

const SESSION_KEY = 'stealthy_auth_session';

export function getSession(): AuthSession | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as AuthSession;
  } catch {
    return null;
  }
}

export function setSession(session: AuthSession): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(SESSION_KEY, JSON.stringify(session));
  // Also dispatch a custom event so UI components can react to auth changes
  window.dispatchEvent(new Event('stealthy-auth-change'));
}

export function clearSession(): void {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(SESSION_KEY);
  window.dispatchEvent(new Event('stealthy-auth-change'));
}

export function isAuthenticated(): boolean {
  const session = getSession();
  return !!(session && session.accessToken);
}

export function getAccountId(): string | null {
  const session = getSession();
  return session ? session.accountId : null;
}

const DEVICE_GUID_KEY = 'stealthy_device_guid';

export function getOrCreateDeviceGuid(): string {
  if (typeof window === 'undefined') return 'server-side-render';
  let guid = localStorage.getItem(DEVICE_GUID_KEY);
  if (!guid) {
    guid = 'WEB-' + Math.random().toString(36).substring(2, 10).toUpperCase() + '-' + Date.now().toString(36).toUpperCase();
    localStorage.setItem(DEVICE_GUID_KEY, guid);
  }
  return guid;
}

// ─── API Error Class ─────────────────────────────────────────────────────────

export class ApiError extends Error {
  public status: number;
  public code?: string;
  public data?: any;

  constructor(message: string, status: number = 500, code?: string, data?: any) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.data = data;
  }
}

// ─── Core API Request Engine ─────────────────────────────────────────────────

interface RequestOptions extends RequestInit {
  timeoutMs?: number;
  skipAuth?: boolean;
  _retryCount?: number;
}

let isRefreshing = false;
let refreshQueue: Array<(token: string | null) => void> = [];

async function performRefresh(): Promise<string | null> {
  const session = getSession();
  if (!session || !session.refreshToken) {
    clearSession();
    return null;
  }

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    const res = await fetch(`${config.apiUrl}/api/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: session.refreshToken }),
      signal: controller.signal,
    });
    clearTimeout(timeout);

    if (res.status === 403) {
      // Possible replay detection or revoked refresh token -> destroy session immediately
      clearSession();
      throw new ApiError('Security violation or session replay detected. Please log in again.', 403, 'ReplayDetected');
    }

    if (!res.ok) {
      clearSession();
      return null;
    }

    const data = await res.json();
    const newSession: AuthSession = {
      accessToken: data.access_token,
      refreshToken: data.refresh_token || session.refreshToken,
      expiresAt: Date.now() + (data.expires_in ? data.expires_in * 1000 : 15 * 60 * 1000),
      accountId: session.accountId,
    };
    setSession(newSession);
    return newSession.accessToken;
  } catch (err) {
    clearSession();
    if (err instanceof ApiError) throw err;
    return null;
  }
}

export async function apiRequest<T = any>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const {
    timeoutMs = 15000,
    skipAuth = false,
    _retryCount = 0,
    headers = {},
    ...rest
  } = options;

  const session = getSession();
  const requestHeaders: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(headers as Record<string, string>),
  };

  if (!skipAuth && session?.accessToken) {
    requestHeaders['Authorization'] = `Bearer ${session.accessToken}`;
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  let response: Response;
  try {
    response = await fetch(`${config.apiUrl}${endpoint}`, {
      ...rest,
      headers: requestHeaders,
      signal: controller.signal,
    });
  } catch (err: any) {
    clearTimeout(timeoutId);
    if (err.name === 'AbortError') {
      throw new ApiError('Request timed out while contacting the Oracle Billing Server.', 408, 'Timeout');
    }
    throw new ApiError('Unable to connect to the Oracle Billing Server. Please check your network connection.', 0, 'Offline');
  } finally {
    clearTimeout(timeoutId);
  }

  // Handle Maintenance Mode (503)
  if (response.status === 503) {
    throw new ApiError('Stealthy Billing Server is currently undergoing scheduled maintenance.', 503, 'MaintenanceMode');
  }

  // Handle Rate Limiting (429)
  if (response.status === 429) {
    throw new ApiError('Too many requests. Please wait a moment before trying again.', 429, 'RateLimited');
  }

  // Handle 401 Unauthorized -> try refresh token once
  if (response.status === 401 && !skipAuth && _retryCount === 0 && session?.refreshToken) {
    if (isRefreshing) {
      // Wait for the ongoing refresh to complete
      const newToken = await new Promise<string | null>((resolve) => {
        refreshQueue.push(resolve);
      });
      if (newToken) {
        return apiRequest<T>(endpoint, { ...options, _retryCount: 1 });
      }
      throw new ApiError('Authentication expired. Please sign in again.', 401, 'Unauthorized');
    }

    isRefreshing = true;
    try {
      const newToken = await performRefresh();
      refreshQueue.forEach((cb) => cb(newToken));
      refreshQueue = [];
      if (newToken) {
        return apiRequest<T>(endpoint, { ...options, _retryCount: 1 });
      }
      throw new ApiError('Authentication expired. Please sign in again.', 401, 'Unauthorized');
    } finally {
      isRefreshing = false;
    }
  }

  // Parse JSON or text response
  let data: any = null;
  const contentType = response.headers.get('content-type');
  if (contentType && contentType.includes('application/json')) {
    try {
      data = await response.json();
    } catch {
      data = null;
    }
  } else {
    try {
      data = await response.text();
    } catch {
      data = null;
    }
  }

  if (!response.ok) {
    const detailMessage = typeof data?.detail === 'string'
      ? data.detail
      : typeof data?.message === 'string'
      ? data.message
      : `Request failed with status ${response.status}`;

    // Check for specific security or business error codes
    let code = 'Error';
    if (response.status === 403) {
      if (detailMessage.toLowerCase().includes('replay')) {
        code = 'ReplayDetected';
        clearSession();
      } else if (detailMessage.toLowerCase().includes('limit')) {
        code = 'DeviceLimitExceeded';
      } else {
        code = 'Forbidden';
      }
    }

    throw new ApiError(detailMessage, response.status, code, data);
  }

  return data as T;
}

// ─── Typed Domain API Methods ────────────────────────────────────────────────

export interface RegisterAccountPayload {
  plan_id?: string;
}

export interface RegisterAccountResponse {
  account_id: string;
  master_token: string;
}

export interface LoginPayload {
  account_id: string;
  master_token: string;
  device_guid: string;
  two_fa_code?: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface AccountMeResponse {
  account_id: string;
  status: string;
  subscription_expires_at: string | null;
  device_count: number;
  plan: string;
  email?: string | null;
  two_factor_enabled?: boolean;
}

export interface DeviceDto {
  device_guid: string;
  friendly_name?: string | null;
  is_active: boolean;
  created_at: string;
  last_seen_at: string;
}

export interface DeviceListResponse {
  devices: DeviceDto[];
}

export interface BillingPaymentDto {
  id: string;
  amount: number;
  currency: string;
  status: string;
  created_at: string;
  description?: string;
}

export const api = {
  // Authentication & Registration
  registerAccount: (payload: RegisterAccountPayload = { plan_id: 'free' }) =>
    apiRequest<RegisterAccountResponse>('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify(payload),
      skipAuth: true,
    }),

  login: (payload: LoginPayload) =>
    apiRequest<LoginResponse>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify(payload),
      skipAuth: true,
    }),

  logout: async () => {
    const session = getSession();
    if (session?.refreshToken) {
      try {
        await apiRequest('/api/auth/logout', {
          method: 'POST',
          body: JSON.stringify({ refresh_token: session.refreshToken }),
        });
      } catch {
        // Ignore network errors during logout
      }
    }
    clearSession();
  },

  // Client Profile & Account
  getClientMe: () => apiRequest<AccountMeResponse>('/api/client/me'),

  // Devices
  listDevices: () => apiRequest<DeviceListResponse>('/api/devices'),

  deactivateDevice: (deviceGuid: string) =>
    apiRequest<{ success: boolean }>(`/api/devices/${encodeURIComponent(deviceGuid)}`, {
      method: 'DELETE',
    }),

  // Read-only Billing History
  getBillingHistory: () => apiRequest<BillingPaymentDto[]>('/api/billing/payments'),
};
