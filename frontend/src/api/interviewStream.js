import { getAccessToken, persistAuth, FETCH_CREDENTIALS } from '../lib/authClient';
import { getApiBaseUrl } from '../utils/apiConfig';

async function refreshAccessToken() {
  const normalizedBase = getApiBaseUrl().replace(/\/$/, '');
  const token = localStorage.getItem('ic_token');
  const headers = { 'Content-Type': 'application/json' };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  const refreshRes = await fetch(`${normalizedBase}/refresh-token`, {
    method: 'POST',
    ...FETCH_CREDENTIALS,
    headers,
  });
  if (!refreshRes.ok) return null;
  const refreshData = await refreshRes.json().catch(() => ({}));
  if (refreshData.token) {
    persistAuth(refreshData.token, refreshData.user || null);
    return refreshData.token;
  }
  if (refreshData.user) {
    persistAuth(null, refreshData.user);
  }
  return refreshRes.ok ? 'cookie' : null;
}

function buildUrl(endpoint) {
  const normalizedBase = getApiBaseUrl().replace(/\/$/, '');
  const clean = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  if (clean.startsWith('/api/') && normalizedBase.endsWith('/api')) {
    return `${normalizedBase}${clean.slice(4)}`;
  }
  return `${normalizedBase}${clean}`;
}

async function postInterviewStreamRequest(endpoint, body, signal) {
  const token = getAccessToken();
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;

  return fetch(buildUrl(endpoint), {
    method: 'POST',
    ...FETCH_CREDENTIALS,
    headers,
    body: JSON.stringify(body),
    signal,
  });
}

/**
 * SSE interview response: started | queued | token | complete | error
 * Falls back to null on failure so caller can use apiPost.
 */
export async function apiPostInterviewStream(endpoint, body, { onEvent, signal } = {}) {
  let response = await postInterviewStreamRequest(endpoint, body, signal);

  if (response.status === 401) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      response = await postInterviewStreamRequest(endpoint, body, signal);
    }
  }

  if (response.status === 401) {
    const err = new Error('Session expired. Please log in again.');
    err.status = 401;
    throw err;
  }

  if (!response.ok || !response.body) {
    return null;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let lastPayload = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split('\n\n');
    buffer = chunks.pop() || '';

    for (const chunk of chunks) {
      const dataLine = chunk.split('\n').find((line) => line.startsWith('data: '));
      if (!dataLine) continue;
      try {
        const payload = JSON.parse(dataLine.slice(6));
        lastPayload = payload;
        onEvent?.(payload);
      } catch {
        // ignore malformed SSE chunks
      }
    }
  }

  return lastPayload;
}
