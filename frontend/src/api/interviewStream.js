import { getAccessToken } from '../lib/authClient';
import { getApiBaseUrl } from '../utils/apiConfig';

function buildUrl(endpoint) {
  const normalizedBase = getApiBaseUrl().replace(/\/$/, '');
  const clean = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  if (clean.startsWith('/api/') && normalizedBase.endsWith('/api')) {
    return `${normalizedBase}${clean.slice(4)}`;
  }
  return `${normalizedBase}${clean}`;
}

/**
 * SSE interview response: events started | complete | error
 * Falls back to null on failure so caller can use apiPost.
 */
export async function apiPostInterviewStream(endpoint, body, { onEvent, signal } = {}) {
  const token = getAccessToken();
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;

  const response = await fetch(buildUrl(endpoint), {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
    signal,
  });

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
      const lines = chunk.split('\n');
      let eventName = 'message';
      let dataLine = '';
      for (const line of lines) {
        if (line.startsWith('event:')) eventName = line.slice(6).trim();
        if (line.startsWith('data:')) dataLine += line.slice(5).trim();
      }
      if (!dataLine) continue;
      let parsed = {};
      try {
        parsed = JSON.parse(dataLine);
      } catch {
        parsed = { raw: dataLine };
      }
      if (onEvent) onEvent(eventName, parsed);
      if (eventName === 'complete') lastPayload = parsed;
      if (eventName === 'error') {
        const err = new Error(parsed.message || 'Interview stream failed');
        err.payload = parsed;
        err.busy = parsed.busy;
        err.closed = parsed.closed;
        throw err;
      }
    }
  }

  return lastPayload;
}
