import { createContext, useContext, useEffect, useState, useMemo } from 'react';
import {
  getAccessToken,
  getStoredUser,
  signIn,
  signOut,
  signUp,
  verifyEmail,
  resendVerification,
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

  const signup = async (username, email, password, full_name = '') => {
    const data = await signUp({ username, email, password, fullName: full_name });
    if (data.user && data.token) {
      setUser(data.user);
    } else {
      setUser(null);
    }
    return data;
  };

  const login = async (identifier, password) => {
    const data = await signIn({ identifier, password });
    setUser(data.user);
    return data;
  };

  const confirmEmail = async (token) => {
    const data = await verifyEmail(token);
    setUser(data.user);
    return data;
  };

  const resendVerificationEmail = async (email) => resendVerification(email);

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
    confirmEmail,
    resendVerificationEmail,
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
