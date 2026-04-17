import { getApiBaseUrl } from '../utils/apiConfig';

const API_BASE = getApiBaseUrl();

const normalizeUser = (user) => {
  if (!user) return null;
  return {
    ...user,
    user_metadata: {
      full_name: user.full_name || user.user_metadata?.full_name || '',
      avatar_url: user.avatar_url || user.user_metadata?.avatar_url || '',
    },
  };
};

export const getAccessToken = () => localStorage.getItem('ic_token');

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
