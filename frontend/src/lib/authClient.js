import { getApiBaseUrl } from '../utils/apiConfig';

const API_BASE = getApiBaseUrl();

const decodeJwtPayload = (token) => {
  if (!token) return null;
  try {
    const [, payload] = token.split('.');
    if (!payload) return null;
    const normalized = payload.replace(/-/g, '+').replace(/_/g, '/');
    const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '=');
    return JSON.parse(atob(padded));
  } catch {
    return null;
  }
};

export const isTokenExpired = (token, clockSkewSeconds = 30) => {
  const payload = decodeJwtPayload(token);
  if (!payload?.exp) {
    return false;
  }
  return payload.exp * 1000 <= Date.now() + clockSkewSeconds * 1000;
};

const normalizeUser = (user) => {
  if (!user) return null;
  const full_name = user.full_name || user.user_metadata?.full_name || '';
  const nickname = user.nickname || user.user_metadata?.nickname || '';
  const avatar_url = user.avatar_url || user.user_metadata?.avatar_url || '';
  const date_of_birth = user.date_of_birth || user.user_metadata?.date_of_birth || '';
  return {
    ...user,
    full_name,
    nickname,
    avatar_url,
    date_of_birth,
    user_metadata: {
      ...user.user_metadata,
      full_name,
      nickname,
      avatar_url,
      date_of_birth,
    },
  };
};

export const getAccessToken = () => {
  const token = localStorage.getItem('ic_token');
  if (!token) return null;
  if (isTokenExpired(token)) {
    clearStoredAuth();
    return null;
  }
  return token;
};

export const getStoredUser = () => {
  try {
    return normalizeUser(JSON.parse(localStorage.getItem('ic_user')));
  } catch {
    return null;
  }
};

export const clearStoredAuth = () => {
  localStorage.removeItem('ic_token');
  localStorage.removeItem('ic_user');
};

export const persistAuth = (token, user) => {
  if (token) {
    localStorage.setItem('ic_token', token);
  }
  if (user) {
    localStorage.setItem('ic_user', JSON.stringify(normalizeUser(user)));
  }
};

export const getSession = async () => {
  const token = getAccessToken();
  const user = getStoredUser();
  if (!token || !user) {
    return null;
  }
  return { access_token: token, user };
};

export const getAuthHeaders = (headers = {}) => {
  const token = getAccessToken();
  return {
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...headers,
  };
};

export const refreshCurrentUser = async (token = getAccessToken()) => {
  if (!token) return null;
  const response = await fetch(`${API_BASE}/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) return null;
  const user = normalizeUser(payload.user);
  persistAuth(token, user);
  return user;
};

export const signUp = async ({ username, email, password, fullName = '' }) => {
  const response = await fetch(`${API_BASE}/signup`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      username: username.toLowerCase().trim(),
      email: email.toLowerCase().trim(),
      password,
      full_name: fullName.trim(),
    }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || 'Signup failed');
  }
  const user = normalizeUser(data.user);
  if (data.token) {
    persistAuth(data.token, user);
  } else {
    clearStoredAuth();
  }
  return { token: data.token, user, ...data };
};

export const signIn = async ({ identifier, password }) => {
  const response = await fetch(`${API_BASE}/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      identifier: identifier.toLowerCase().trim(),
      password,
    }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || 'Login failed');
  }
  const user = normalizeUser(data.user);
  persistAuth(data.token, user);
  return { token: data.token, user };
};

export const resendVerification = async (email) => {
  const response = await fetch(`${API_BASE}/resend-verification`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: email.toLowerCase().trim() }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || 'Unable to resend verification email');
  }
  return data;
};

export const verifyEmail = async (token) => {
  const response = await fetch(`${API_BASE}/verify-email?token=${encodeURIComponent(token)}`);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || 'Email verification failed');
  }
  const user = normalizeUser(data.user);
  persistAuth(data.token, user);
  return { token: data.token, user, ...data };
};

export const signOut = async () => {
  clearStoredAuth();
};

export const updateCurrentUser = async (payload = {}) => {
  const response = await fetch(`${API_BASE}/me`, {
    method: 'PUT',
    headers: {
      ...getAuthHeaders(),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || data.message || 'Profile update failed');
  }
  const user = normalizeUser(data.user);
  persistAuth(getAccessToken(), user);
  return user;
};

export const isValidEmail = (email) => /\S+@\S+\.\S+/.test(email);

export const formatAuthError = (error) => {
  if (!error) return 'Something went wrong.';
  if (typeof error === 'string') return error;
  return error.message || 'Something went wrong.';
};

export const isValidUsername = (username) => /^[a-zA-Z0-9._-]{3,}$/.test(username);

export const setAccessToken = (token) => {
  if (token) localStorage.setItem('ic_token', token);
};

export const forgotPassword = async (email) => {
  const response = await fetch(`${API_BASE}/forgot-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: email.toLowerCase().trim() }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || data.message || 'Unable to send password reset link');
  }
  return data;
};

export const forgotUsername = async (email) => {
  const response = await fetch(`${API_BASE}/forgot-username`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: email.toLowerCase().trim() }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || data.message || 'Unable to recover username right now');
  }
  return data;
};

export const resetPassword = async (token, password) => {
  const response = await fetch(`${API_BASE}/reset-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token, password }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || 'Password reset failed');
  if (data.token) persistAuth(data.token, null);
  return data;
};

export const deleteAccount = async (password) => {
  const response = await fetch(`${API_BASE}/me`, {
    method: 'DELETE',
    headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify({ password }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || 'Account deletion failed');
  clearStoredAuth();
  return data;
};
