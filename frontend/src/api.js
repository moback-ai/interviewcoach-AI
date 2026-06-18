import { getAccessToken, setAccessToken, persistAuth } from './lib/authClient';
import { redirectToExpiredLogin } from './utils/authInterceptor';
import { getApiBaseUrl } from './utils/apiConfig';

const API_BASE = getApiBaseUrl();

// ── Token helpers ─────────────────────────────────────────────────────────────
export const getToken = () => localStorage.getItem('ic_token');
export const isLoggedIn = () => !!getToken();

function snapshotFormData(formData) {
  if (!(formData instanceof FormData)) {
    return null;
  }
  return Array.from(formData.entries());
}

function rebuildFormData(entries) {
  const formData = new FormData();
  if (!Array.isArray(entries)) {
    return formData;
  }
  entries.forEach(([key, value]) => {
    formData.append(key, value);
  });
  return formData;
}

function getHeaders(isFileUpload = false, { allowExpiredToken = false } = {}) {
  const token = allowExpiredToken
    ? localStorage.getItem('ic_token')
    : getAccessToken();
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  if (!isFileUpload) headers['Content-Type'] = 'application/json';
  return headers;
}

function buildUrl(endpoint) {
  if (endpoint.startsWith('http')) return endpoint;
  const normalizedBase = API_BASE.replace(/\/$/, '');

  if (endpoint === '/api' && normalizedBase.endsWith('/api')) {
    return normalizedBase;
  }

  if (endpoint.startsWith('/api/') && normalizedBase.endsWith('/api')) {
    return `${normalizedBase}${endpoint.slice(4)}`;
  }

  const clean = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  return `${normalizedBase}${clean}`;
}

async function refreshAccessToken() {
  const refreshRes = await fetch(buildUrl('/api/refresh-token'), {
    method: 'POST',
    headers: getHeaders(false, { allowExpiredToken: true }),
  });
  if (!refreshRes.ok) {
    return null;
  }
  const refreshData = await refreshRes.json().catch(() => ({}));
  if (!refreshData.token) {
    return null;
  }
  persistAuth(refreshData.token, refreshData.user || null);
  setAccessToken(refreshData.token);
  return refreshData.token;
}

// ── Core fetch wrapper ────────────────────────────────────────────────────────
export async function apiCall(endpoint, options = {}) {
  try {
    const isFileUpload = options.body instanceof FormData;
    const formDataSnapshot = options._formDataSnapshot || (isFileUpload ? snapshotFormData(options.body) : null);
    const headers = { ...getHeaders(isFileUpload), ...options.headers };
    const { timeoutMs, signal: callerSignal, _retried, _formDataSnapshot, ...restOptions } = options;
    const requestBody = isFileUpload && formDataSnapshot
      ? rebuildFormData(formDataSnapshot)
      : restOptions.body;

    const config = { method: restOptions.method || 'GET', headers, ...restOptions, body: requestBody };
    if (requestBody && !isFileUpload) {
      config.body = JSON.stringify(requestBody);
    }
    if (timeoutMs && typeof AbortSignal !== 'undefined' && typeof AbortSignal.timeout === 'function') {
      config.signal = AbortSignal.timeout(timeoutMs);
    } else if (callerSignal) {
      config.signal = callerSignal;
    }
    const response = await fetch(buildUrl(endpoint), config);

    if (response.status === 401) {
      if (!_retried) {
        const refreshed = await refreshAccessToken();
        if (refreshed) {
          return apiCall(endpoint, {
            ...options,
            _retried: true,
            _formDataSnapshot: formDataSnapshot,
            body: isFileUpload ? rebuildFormData(formDataSnapshot) : restOptions.body,
          });
        }
      }

      redirectToExpiredLogin();
      throw new Error('Session expired. Please log in again.');
    }

    if (response.status === 429) {
      throw new Error('Too many requests. Please wait a moment and try again.');
    }

    if (response.status === 503) {
      try {
        const payload = await response.json();
        if (payload.busy) {
          const err = new Error(payload.message || 'Interview AI is busy. Please try again.');
          err.busy = true;
          err.retryAfter = payload.retry_after;
          throw err;
        }
      } catch (parseErr) {
        if (parseErr.busy) throw parseErr;
      }
    }

    if (!response.ok) {
      let msg = `HTTP ${response.status}`;
      const contentType = response.headers.get('content-type') || '';
      if (contentType.includes('text/html')) {
        if (response.status === 504) {
          throw new Error(
            'The server timed out while processing your request. Try again with a smaller file or paste the job description text manually.'
          );
        }
        throw new Error(`Server error (${response.status}). Please try again in a moment.`);
      }
      try { const e = await response.json(); msg = e.error || e.message || msg; } catch {}
      throw new Error(msg);
    }
    try { return await response.json(); } catch { return { data: await response.text() }; }
  } catch (error) {
    console.error('API error:', error);
    throw error;
  }
}

// ── Convenience wrappers ──────────────────────────────────────────────────────
export const apiGet    = (ep, opts = {})       => apiCall(ep, { method: 'GET',    ...opts });
export const apiPost   = (ep, data, opts = {}) => apiCall(ep, { method: 'POST',   body: data, ...opts });
export const apiPut    = (ep, data, opts = {}) => apiCall(ep, { method: 'PUT',    body: data, ...opts });
export const apiDelete = (ep, opts = {})       => apiCall(ep, { method: 'DELETE', ...opts });

export async function uploadFile(endpoint, formData, opts = {}) {
  const normalizedEndpoint = endpoint.startsWith('/api/')
    ? endpoint
    : `/api${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
  return apiCall(normalizedEndpoint, {
    method: 'POST',
    body: formData,
    _formDataSnapshot: snapshotFormData(formData),
    ...opts,
  });
}

// ── Auth helpers ──────────────────────────────────────────────────────────────
export const forgotPassword = (email) =>
  apiPost('/api/forgot-password', { email });

export const resetPassword = (token, password) =>
  apiPost('/api/reset-password', { token, password });

export const deleteAccount = (password) =>
  apiCall('/api/me', { method: 'DELETE', body: { password } });

export const getInterviewHistory = (page = 1, limit = 10) =>
  apiGet(`/api/interview-history?page=${page}&limit=${limit}`);

export const getDashboard = (page = 1, limit = 20) =>
  apiGet(`/api/dashboard?page=${page}&limit=${limit}`);
