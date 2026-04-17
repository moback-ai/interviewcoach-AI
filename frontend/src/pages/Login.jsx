import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { FiEye, FiEyeOff } from 'react-icons/fi';
import Navbar from '../components/Navbar';
import { useTheme } from '../hooks/useTheme';
import { useAuth } from '../contexts/AuthContext';
import { isValidEmail } from '../lib/authClient';
import { performSmartRedirect } from '../utils/smartRouting';
import { trackEvents } from '../services/mixpanel';
import { checkEmailAvailability } from '../utils/emailAvailability';

function Login() {
  const navigate = useNavigate();
  useTheme();
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [passwordVisible, setPasswordVisible] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setErrorMsg('');

    try {
      const data = await login(email, password);

      trackEvents.signIn({
        email,
        user_id: data.user?.id,
        login_timestamp: new Date().toISOString(),
      });

      performSmartRedirect(navigate);
    } catch (error) {
      const message = (error.message || '').toLowerCase();
      if (message.includes('invalid credentials')) {
        try {
          const availability = await checkEmailAvailability(email.toLowerCase().trim());
          setErrorMsg(
            availability.available
              ? 'This email is not registered. Please sign up first.'
              : 'Invalid password. Please try again.'
          );
        } catch {
          setErrorMsg('Invalid email or password.');
        }
      } else {
        setErrorMsg(error.message || 'Unable to log in right now.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Navbar />
      <div className="min-h-screen flex items-center justify-center bg-[var(--color-bg)] px-4 py-8">
        <div className="w-full max-w-md bg-[var(--color-card)] text-[var(--color-text-primary)] p-8 rounded-2xl shadow-lg border border-[var(--color-border)]">
          <h2 className="text-3xl font-bold text-center mb-6 text-[var(--color-primary)]">Welcome Back</h2>

          {errorMsg && (
            <div className="mb-4 p-3 rounded-lg bg-red-50 border border-red-200 text-red-600 text-sm text-center">
              {errorMsg}
            </div>
          )}

          <form onSubmit={handleLogin} className="space-y-5">
            <div>
              <label className="block text-sm font-medium mb-1 text-[var(--color-text-secondary)]">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                disabled={loading}
                className="w-full px-4 py-2 rounded-lg bg-[var(--color-input-bg)] border border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] transition"
                placeholder="you@example.com"
              />
              {email && !isValidEmail(email) && (
                <p className="text-xs text-red-500 mt-1">Enter a valid email address.</p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium mb-1 text-[var(--color-text-secondary)]">Password</label>
              <div className="relative">
                <input
                  type={passwordVisible ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  disabled={loading}
                  className="w-full px-4 py-2 rounded-lg bg-[var(--color-input-bg)] border border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] transition pr-10"
                  placeholder="Enter your password"
                />
                <button
                  type="button"
                  onClick={() => setPasswordVisible((prev) => !prev)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--color-text-secondary)]"
                >
                  {passwordVisible ? <FiEyeOff /> : <FiEye />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading || !isValidEmail(email) || !password}
              className="w-full py-2.5 rounded-lg bg-[var(--color-primary)] text-white font-medium hover:opacity-90 transition disabled:opacity-50"
            >
              {loading ? 'Signing in...' : 'Login'}
            </button>
          </form>

          <p className="text-sm text-center mt-6 text-[var(--color-text-secondary)]">
            Don&apos;t have an account?{' '}
            <Link to="/signup" className="text-[var(--color-primary)] hover:underline">
              Create one
            </Link>
          </p>
        </div>
      </div>
    </>
  );
}

export default Login;
