import { getApiBaseUrl, getStorageBaseUrl } from './utils/apiConfig';

const API_BASE = getApiBaseUrl();
const STORAGE_BASE = getStorageBaseUrl();

const getToken = () => localStorage.getItem('ic_token');
const getStoredUser = () => {
  try {
    return JSON.parse(localStorage.getItem('ic_user'));
  } catch {
    return null;
  }
};

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

const persistAuth = (token, user) => {
  if (token) localStorage.setItem('ic_token', token);
  if (user) localStorage.setItem('ic_user', JSON.stringify(normalizeUser(user)));
};

const clearAuth = () => {
  localStorage.removeItem('ic_token');
  localStorage.removeItem('ic_user');
};

async function apiFetch(path, opts = {}) {
  const token = getToken();
  const isForm = opts.body instanceof FormData;
  const headers = {
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(!isForm ? { 'Content-Type': 'application/json' } : {}),
    ...opts.headers,
  };
  const response = await fetch(`${API_BASE}${path}`, { ...opts, headers });
  const data = await response.json().catch(() => ({}));
  return { response, data, error: response.ok ? null : { message: data.error || data.message || 'Request failed' } };
}

async function fetchCurrentUser(token = getToken()) {
  if (!token) return null;
  const response = await fetch(`${API_BASE}/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const payload = await response.json().catch(() => ({}));
  return response.ok ? normalizeUser(payload.user) : null;
}

const auth = {
  async signUp({ email, password, options }) {
    const res = await fetch(`${API_BASE}/signup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email,
        password,
        full_name: options?.data?.full_name || '',
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) return { data: null, error: { message: data.error || 'Signup failed' } };
    const user = normalizeUser(data.user);
    persistAuth(data.token, user);
    return { data: { user, session: { access_token: data.token, user } }, error: null };
  },

  async signInWithPassword({ email, password }) {
    const res = await fetch(`${API_BASE}/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) return { data: null, error: { message: data.error || 'Login failed' } };
    const user = normalizeUser(data.user);
    persistAuth(data.token, user);
    return { data: { user, session: { access_token: data.token, user } }, error: null };
  },

  async signOut() {
    clearAuth();
    return { error: null };
  },

  async getUser() {
    const user = normalizeUser(getStoredUser());
    return { data: { user }, error: null };
  },

  async getSession() {
    const token = getToken();
    const user = normalizeUser(getStoredUser());
    if (!token || !user) return { data: { session: null }, error: null };
    return { data: { session: { access_token: token, refresh_token: token, user } }, error: null };
  },

  async setSession({ access_token }) {
    if (!access_token) {
      clearAuth();
      return { data: { session: null }, error: { message: 'Missing access token' } };
    }
    const user = await fetchCurrentUser(access_token);
    if (!user) return { data: { session: null }, error: { message: 'Session invalid or expired' } };
    persistAuth(access_token, user);
    return { data: { session: { access_token, refresh_token: access_token, user } }, error: null };
  },

  onAuthStateChange(callback) {
    const user = normalizeUser(getStoredUser());
    const token = getToken();
    if (user && token) {
      setTimeout(() => callback('SIGNED_IN', { user, access_token: token, refresh_token: token }), 0);
    }
    return { data: { subscription: { unsubscribe: () => {} } } };
  },

  async resetPasswordForEmail() {
    return { error: null };
  },

  async updateUser(payload = {}) {
    const body = {
      ...(payload.data || {}),
      ...(payload.password ? { password: payload.password } : {}),
    };
    const { data, error } = await apiFetch('/me', {
      method: 'PUT',
      body: JSON.stringify(body),
    });
    if (error) return { data: null, error };
    const nextUser = normalizeUser(data.user || getStoredUser());
    persistAuth(getToken(), nextUser);
    return { data: { user: nextUser }, error: null };
  },

  async resend() {
    return { error: null };
  },

  async signInWithOAuth() {
    return { error: { message: 'OAuth is not enabled in the self-hosted auth flow.' } };
  },
};

function storageBucket(bucket) {
  return {
    async upload(path, file) {
      const form = new FormData();
      form.append('file', file instanceof Blob ? file : new Blob([file]));
      form.append('path', path);
      form.append('bucket', bucket);
      const { data, error } = await apiFetch('/upload-resume', {
        method: 'POST',
        body: form,
      });
      return { data, error };
    },

    getPublicUrl(path) {
      return `${STORAGE_BASE}/${path}`;
    },

    async download(path) {
      const response = await fetch(`${STORAGE_BASE}/${path}`, {
        headers: getToken() ? { Authorization: `Bearer ${getToken()}` } : {},
      });
      return {
        data: response.ok ? await response.blob() : null,
        error: response.ok ? null : { message: 'Download failed' },
      };
    },

    async list(path) {
      const { data, error } = await apiFetch(`/list-files?folder=${path}`);
      return { data, error };
    },

    async remove(paths) {
      const { data, error } = await apiFetch('/delete-files', {
        method: 'DELETE',
        body: JSON.stringify({ paths }),
      });
      return { data, error };
    },
  };
}

const storage = {
  from: (bucket) => storageBucket(bucket),
};

function dbTable(table) {
  if (table === 'overall_evaluation') {
    return {
      select: () => ({
        order: () => ({
          limit: () => ({
            single: async () => {
              const { data, error } = await apiFetch('/overall-performance');
              return { data: data?.data?.[0] || null, error };
            },
          }),
        }),
      }),
    };
  }

  return {
    select: () => ({
      eq: async (col, val) => {
        const { data, error } = await apiFetch(`/${table}?${col}=${encodeURIComponent(val)}`);
        return { data: data?.data || data, error };
      },
      order: () => ({ data: [], error: null }),
      limit: () => ({ data: [], error: null }),
      single: async () => {
        const { data, error } = await apiFetch(`/${table}?single=true`);
        return { data: data?.data || data || null, error };
      },
    }),
    insert: async (rows) => {
      const { data, error } = await apiFetch(`/${table}`, { method: 'POST', body: JSON.stringify(rows) });
      return { data: data?.data || data, error };
    },
    update: (payload) => ({
      eq: async (_col, val) => {
        const { data, error } = await apiFetch(`/${table}/${val}`, { method: 'PUT', body: JSON.stringify(payload) });
        return { data: data?.data || data, error };
      },
    }),
    delete: () => ({
      eq: async (_col, val) => {
        const { data, error } = await apiFetch(`/${table}/${val}`, { method: 'DELETE' });
        return { data: data?.data || data, error };
      },
    }),
    upsert: async (payload) => {
      const { data, error } = await apiFetch(`/${table}`, { method: 'POST', body: JSON.stringify(payload) });
      return { data: data?.data || data, error };
    },
  };
}

export const supabase = {
  auth,
  storage,
  from: (table) => dbTable(table),
};

export default supabase;
