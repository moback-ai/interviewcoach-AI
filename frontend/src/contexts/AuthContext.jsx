import { createContext, useContext, useEffect, useState, useMemo } from 'react';
import {
  getAccessToken,
  getStoredUser,
  signIn,
  signOut,
  signUp,
  updateCurrentUser,
} from '../lib/authClient';
import { getApiBaseUrl } from '../utils/apiConfig';

const AuthContext = createContext();
const API_BASE = getApiBaseUrl();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // Load user from localStorage on mount
  useEffect(() => {
    const storedUser = getStoredUser();
    const token = getAccessToken();
    if (storedUser && token) {
      setUser(storedUser);
    }
    setLoading(false);
  }, []);

  const signup = async (email, password, full_name = '') => {
    const data = await signUp({ email, password, fullName: full_name });
    setUser(data.user);
    return data;
  };

  const login = async (email, password) => {
    const data = await signIn({ email, password });
    setUser(data.user);
    return data;
  };

  const logout = async () => {
    await signOut();
    setUser(null);
    window.location.href = '/login';
  };

  const getToken = () => getAccessToken();

  const updateProfile = async (payload) => {
    const nextUser = await updateCurrentUser(payload);
    setUser(nextUser);
    return nextUser;
  };

  const value = useMemo(() => ({
    user,
    loading,
    isAuthenticated: !!user,
    signup,
    login,
    logout,
    getToken,
    updateProfile,
    apiBase: API_BASE,
  }), [user, loading, API_BASE]);

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
