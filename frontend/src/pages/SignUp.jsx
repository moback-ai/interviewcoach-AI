import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { FiEye, FiEyeOff } from 'react-icons/fi';
import Navbar from '../components/Navbar';
import { useTheme } from '../hooks/useTheme';
import { useAuth } from '../contexts/AuthContext';
import { formatAuthError, isValidEmail } from '../lib/authClient';
import { performSmartRedirect } from '../utils/smartRouting';
import { trackEvents } from '../services/mixpanel';
import { checkEmailAvailability } from '../utils/emailAvailability';

function Signup() {
  const navigate = useNavigate();
  useTheme();
  const { signup } = useAuth();
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [acceptedTerms, setAcceptedTerms] = useState(false);
  const [passwordVisible, setPasswordVisible] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  const handleSignup = async (e) => {
    e.preventDefault();
    setLoading(true);
    setErrorMsg('');

    try {
      const availability = await checkEmailAvailability(email.toLowerCase().trim());
      if (!availability.available) {
        throw new Error('This email is already registered. Please log in instead.');
      }

      const data = await signup(email, password, fullName);

      trackEvents.signUp({
        email,
        user_id: data.user?.id,
        full_name: fullName.trim(),
        signup_timestamp: new Date().toISOString(),
      });

      performSmartRedirect(navigate);
    } catch (error) {
      setErrorMsg(formatAuthError(error));
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Navbar />
      <div className="min-h-screen flex items-center justify-center bg-[var(--color-bg)] px-4 py-8">
        <div className="w-full max-w-md bg-[var(--color-card)] text-[var(--color-text-primary)] p-8 rounded-2xl shadow-lg border border-[var(--color-border)]">
          <h2 className="text-3xl font-bold text-center mb-6 text-[var(--color-primary)]">Create Account</h2>

          {errorMsg && (
            <div className="mb-4 p-3 rounded-lg bg-red-50 border border-red-200 text-red-600 text-sm text-center">
              {errorMsg}
            </div>
          )}

          <form onSubmit={handleSignup} className="space-y-5">
            <div>
              <label className="block text-sm font-medium mb-1 text-[var(--color-text-secondary)]">Full Name</label>
              <input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                required
                disabled={loading}
                className="w-full px-4 py-2 rounded-lg bg-[var(--color-input-bg)] border border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] transition"
                placeholder="Your full name"
              />
            </div>

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
            </div>

            <div>
              <label className="block text-sm font-medium mb-1 text-[var(--color-text-secondary)]">Password</label>
              <div className="relative">
                <input
                  type={passwordVisible ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={8}
                  disabled={loading}
                  className="w-full px-4 py-2 rounded-lg bg-[var(--color-input-bg)] border border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] transition pr-10"
                  placeholder="At least 8 characters"
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

            <label className="flex items-start gap-3 text-sm text-[var(--color-text-secondary)]">
              <input
                type="checkbox"
                checked={acceptedTerms}
                onChange={(e) => setAcceptedTerms(e.target.checked)}
                className="mt-1"
              />
              <span>I agree to the Terms and Privacy Policy.</span>
            </label>

            <button
              type="submit"
              disabled={loading || !fullName.trim() || !isValidEmail(email) || password.length < 8 || !acceptedTerms}
              className="w-full py-2.5 rounded-lg bg-[var(--color-primary)] text-white font-medium hover:opacity-90 transition disabled:opacity-50"
            >
              {loading ? 'Creating account...' : 'Sign Up'}
            </button>
          </form>

          <p className="text-sm text-center mt-6 text-[var(--color-text-secondary)]">
            Already have an account?{' '}
            <Link to="/login" className="text-[var(--color-primary)] hover:underline">
              Login
            </Link>
          </p>
        </div>
      </div>
    </>
  );
}

export default Signup;
