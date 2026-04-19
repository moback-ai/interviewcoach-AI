import { getAccessToken, setAccessToken } from './lib/authClient';
import { getApiBaseUrl } from './utils/apiConfig';

const API_BASE = getApiBaseUrl();

// ── Token helpers ─────────────────────────────────────────────────────────────
export const getToken = () => localStorage.getItem('ic_token');
export const isLoggedIn = () => !!getToken();

function getHeaders(isFileUpload = false) {
  const token = getAccessToken();
  const headers = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  if (!isFileUpload) headers['Content-Type'] = 'application/json';
  return headers;
}

function buildUrl(endpoint) {
  if (endpoint.startsWith('http')) return endpoint;
  const clean = endpoint.startsWith('/') ? endpoint.slice(1) : endpoint;
  return `${API_BASE.replace(/\/$/, '')}/${clean}`;
}

// ── Core fetch wrapper ────────────────────────────────────────────────────────
export async function apiCall(endpoint, options = {}) {
  try {
    const isFileUpload = options.body instanceof FormData;
    const headers = { ...getHeaders(isFileUpload), ...options.headers };
    const config = { method: options.method || 'GET', headers, ...options };
    if (options.body && !isFileUpload) {
      config.body = JSON.stringify(options.body);
    }
    const response = await fetch(buildUrl(endpoint), config);

    // Auto-refresh token on 401
    if (response.status === 401 && !options._retried) {
      try {
        const refreshRes = await fetch(buildUrl('/api/refresh-token'), {
          method: 'POST',
          headers: getHeaders(),
        });
        if (refreshRes.ok) {
          const refreshData = await refreshRes.json();
          if (refreshData.token) {
            setAccessToken(refreshData.token);
            return apiCall(endpoint, { ...options, _retried: true });
          }
        }
      } catch {}
      // Refresh failed — let original 401 bubble up
    }

    if (response.status === 429) {
      throw new Error('Too many requests. Please wait a moment and try again.');
    }

    if (!response.ok) {
      let msg = `HTTP ${response.status}`;
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
  return apiCall(endpoint, { method: 'POST', body: formData, ...opts });
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
