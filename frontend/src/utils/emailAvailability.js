import { getApiBaseUrl } from './apiConfig';

const API_BASE = getApiBaseUrl();

export async function checkEmailAvailability(email) {
  try {
    const res = await fetch(`${API_BASE}/check-email`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email })
    });
    const data = await res.json();
    return { exists: data.exists, available: !data.exists };
  } catch {
    return { exists: false, available: true };
  }
}
