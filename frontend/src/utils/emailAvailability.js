import { getApiBaseUrl } from './apiConfig';

const API_BASE = getApiBaseUrl();

export async function checkEmailAvailability(email) {
  try {
    const res = await fetch(`${API_BASE}/check-email`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email })
    });
    if (!res.ok) return { exists: false, available: true, networkError: true };
    const data = await res.json();
    return { exists: data.exists, available: !data.exists };
  } catch {
    return { exists: false, available: true, networkError: true };
  }
}

export async function checkUsernameAvailability(username) {
  try {
    const res = await fetch(`${API_BASE}/check-username`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username })
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      return {
        exists: false,
        available: false,
        error: data.error || 'Could not check username availability.',
      };
    }
    return { exists: data.exists, available: !data.exists, error: data.error || '' };
  } catch {
    return {
      exists: false,
      available: false,
      error: 'Could not check username availability.',
    };
  }
}
