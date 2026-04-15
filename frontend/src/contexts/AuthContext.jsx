import { createContext, useContext, useEffect, useState, useMemo } from 'react';

const AuthContext = createContext();

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000/api';

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // Load user from localStorage on mount
  useEffect(() => {
    const stored = localStorage.getItem('ic_user');
    const token = localStorage.getItem('ic_token');
    if (stored && token) {
      try {
        setUser(JSON.parse(stored));
      } catch (e) {
        localStorage.removeItem('ic_user');
        localStorage.removeItem('ic_token');
      }
    }
    setLoading(false);
  }, []);

  const signup = async (email, password, full_name = '') => {
    const res = await fetch(`${API_BASE}/signup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, full_name })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Signup failed');
    localStorage.setItem('ic_token', data.token);
    localStorage.setItem('ic_user', JSON.stringify(data.user));
    setUser(data.user);
    return data;
  };

  const login = async (email, password) => {
    const res = await fetch(`${API_BASE}/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Login failed');
    localStorage.setItem('ic_token', data.token);
    localStorage.setItem('ic_user', JSON.stringify(data.user));
    setUser(data.user);
    return data;
  };

  const logout = () => {
    localStorage.removeItem('ic_token');
    localStorage.removeItem('ic_user');
    setUser(null);
    window.location.href = '/login';
  };

  const getToken = () => localStorage.getItem('ic_token');

  const value = useMemo(() => ({
    user,
    loading,
    isAuthenticated: !!user,
    signup,
    login,
    logout,
    getToken,
    // Shim for any code that still calls supabase.auth.signOut()
    auth: {
      signOut: logout,
      getSession: async () => ({ data: { session: { access_token: getToken() } } }),
      getUser: async () => ({ data: { user }, error: null }),
      onAuthStateChange: (cb) => {
        // No-op shim — returns unsubscribe shape
        return { data: { subscription: { unsubscribe: () => {} } } };
      }
    }
  }), [user, loading]);

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) throw new Error('useAuth must be used within AuthProvider');
  return context;
};
