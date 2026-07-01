import { createContext, useContext, useEffect, useState, useMemo } from 'react';
import {
  clearStoredAuth,
  fetchCurrentUser,
  getStoredUser,
  signIn,
  signOut,
  signUp,
  verifyEmail,
  resendVerification,
  updateCurrentUser,
} from '../lib/authClient';
import { redirectToExpiredLogin } from '../utils/authInterceptor';
import { getApiBaseUrl } from '../utils/apiConfig';

const AuthContext = createContext();
const API_BASE = getApiBaseUrl();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    const bootstrap = async () => {
      const cachedUser = getStoredUser();
      if (cachedUser) {
        setUser(cachedUser);
      }

      try {
        const liveUser = await fetchCurrentUser();
        if (cancelled) return;
        if (liveUser) {
          setUser(liveUser);
        } else {
          clearStoredAuth();
          setUser(null);
        }
      } catch {
        if (!cancelled && !cachedUser) {
          clearStoredAuth();
          setUser(null);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    bootstrap();
    return () => {
      cancelled = true;
    };
  }, []);

  const signup = async (username, email, password, full_name = '') => {
    const data = await signUp({ username, email, password, fullName: full_name });
    if (data.user) {
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

  const logout = async ({ expired = false } = {}) => {
    await signOut();
    setUser(null);
    if (expired) {
      redirectToExpiredLogin();
      return;
    }
    window.location.href = '/login';
  };

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
    updateProfile,
    apiBase: API_BASE,
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
