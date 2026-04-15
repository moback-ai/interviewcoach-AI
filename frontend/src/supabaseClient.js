// ── Supabase shim ─────────────────────────────────────────────────────────────
// This file replaces the real Supabase client.
// All components that import { supabase } from './supabaseClient' will get
// this shim which routes to our own Flask JWT API instead.

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000/api';

const getToken = () => localStorage.getItem('ic_token');
const getUser  = () => { try { return JSON.parse(localStorage.getItem('ic_user')); } catch { return null; } };

async function apiFetch(path, opts = {}) {
  const token = getToken();
  const isForm = opts.body instanceof FormData;
  const headers = { ...(token ? { Authorization: `Bearer ${token}` } : {}),
                    ...(!isForm ? { 'Content-Type': 'application/json' } : {}),
                    ...opts.headers };
  const res = await fetch(`${API_BASE}${path}`, { ...opts, headers });
  const data = await res.json().catch(() => ({}));
  return { data, error: res.ok ? null : { message: data.error || 'Request failed' } };
}

// ── Auth shim ─────────────────────────────────────────────────────────────────
const auth = {
  async signUp({ email, password, options }) {
    const body = { email, password, full_name: options?.data?.full_name || '' };
    const res = await fetch(`${API_BASE}/signup`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    const data = await res.json();
    if (!res.ok) return { data: null, error: { message: data.error || 'Signup failed' } };
    localStorage.setItem('ic_token', data.token);
    localStorage.setItem('ic_user', JSON.stringify(data.user));
    return { data: { user: data.user, session: { access_token: data.token } }, error: null };
  },

  async signInWithPassword({ email, password }) {
    const res = await fetch(`${API_BASE}/login`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    const data = await res.json();
    if (!res.ok) return { data: null, error: { message: data.error || 'Login failed' } };
    localStorage.setItem('ic_token', data.token);
    localStorage.setItem('ic_user', JSON.stringify(data.user));
    return { data: { user: data.user, session: { access_token: data.token } }, error: null };
  },

  async signOut() {
    localStorage.removeItem('ic_token');
    localStorage.removeItem('ic_user');
    return { error: null };
  },

  async getUser() {
    const user = getUser();
    return { data: { user }, error: null };
  },

  async getSession() {
    const token = getToken();
    const user = getUser();
    if (!token || !user) return { data: { session: null }, error: null };
    return { data: { session: { access_token: token, user } }, error: null };
  },

  onAuthStateChange(callback) {
    // Fire once with current state
    const user = getUser();
    const token = getToken();
    if (user && token) {
      setTimeout(() => callback('SIGNED_IN', { user, access_token: token }), 0);
    }
    return { data: { subscription: { unsubscribe: () => {} } } };
  },

  async resetPasswordForEmail(email) {
    // Not implemented — return mock success
    console.warn('resetPasswordForEmail: not implemented in custom auth');
    return { error: null };
  },

  async updateUser({ password }) {
    // Not implemented
    console.warn('updateUser: not implemented in custom auth');
    return { data: { user: getUser() }, error: null };
  },

  async signInWithOAuth() {
    console.warn('OAuth not supported in custom auth');
    return { error: { message: 'OAuth not supported' } };
  }
};

// ── Storage shim ──────────────────────────────────────────────────────────────
function storageBucket(bucket) {
  return {
    async upload(path, file, opts) {
      const form = new FormData();
      form.append('file', file instanceof Blob ? file : new Blob([file]));
      form.append('path', path);
      form.append('bucket', bucket);
      const res = await fetch(`${API_BASE}/upload-resume`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${getToken()}` },
        body: form
      });
      const data = await res.json();
      return { data, error: res.ok ? null : { message: data.message } };
    },

    getPublicUrl(path) {
      const storageUrl = import.meta.env.VITE_STORAGE_URL || `${API_BASE.replace('/api', '')}/storage`;
      return `${storageUrl}/${path}`;
    },

    async download(path) {
      const storageUrl = import.meta.env.VITE_STORAGE_URL || `${API_BASE.replace('/api', '')}/storage`;
      const res = await fetch(`${storageUrl}/${path}`, {
        headers: { Authorization: `Bearer ${getToken()}` }
      });
      return { data: await res.blob(), error: res.ok ? null : { message: 'Download failed' } };
    },

    async list(path) {
      const res = await apiFetch(`/list-files?folder=${path}`);
      return res;
    },

    async remove(paths) {
      const res = await apiFetch('/delete-files', {
        method: 'DELETE',
        body: JSON.stringify({ paths })
      });
      return res;
    }
  };
}

const storage = {
  from: (bucket) => storageBucket(bucket)
};

// ── DB shim (from() queries — redirect to our REST API) ───────────────────────
function dbTable(table) {
  return {
    select: (cols = '*') => ({
      eq: (col, val) => apiFetch(`/${table}?${col}=${val}`),
      order: () => ({ data: [], error: null }),
      limit: () => ({ data: [], error: null }),
      single: () => apiFetch(`/${table}?single=true`)
    }),
    insert: (rows) => apiFetch(`/${table}`, { method: 'POST', body: JSON.stringify(rows) }),
    update: (data) => ({
      eq: (col, val) => apiFetch(`/${table}/${val}`, { method: 'PUT', body: JSON.stringify(data) })
    }),
    delete: () => ({
      eq: (col, val) => apiFetch(`/${table}/${val}`, { method: 'DELETE' })
    }),
    upsert: (data) => apiFetch(`/${table}`, { method: 'POST', body: JSON.stringify(data) })
  };
}

// ── Main export ───────────────────────────────────────────────────────────────
export const supabase = {
  auth,
  storage,
  from: (table) => dbTable(table)
};

export default supabase;
