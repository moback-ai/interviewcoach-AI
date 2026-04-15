const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000/api';

// ── Token helpers ─────────────────────────────────────────────────────────────
export const getToken = () => localStorage.getItem('ic_token');
export const isLoggedIn = () => !!getToken();

function getHeaders(isFileUpload = false) {
  const token = getToken();
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
