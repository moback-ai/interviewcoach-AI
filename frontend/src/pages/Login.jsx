import React, { useState, useRef } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { FiEye, FiEyeOff, FiCheck, FiX, FiLoader } from 'react-icons/fi';
import { useEffect } from 'react';
import Navbar from '../components/Navbar';
import { useTheme } from '../hooks/useTheme';
import { useAuth } from '../contexts/AuthContext';
import { isValidEmail, isValidUsername } from '../lib/authClient';
import { performSmartRedirect } from '../utils/smartRouting';
import { trackEvents } from '../services/mixpanel';
import { checkEmailAvailability, checkUsernameAvailability } from '../utils/emailAvailability';

function Login() {
  const navigate = useNavigate();
  const location = useLocation();
  useTheme();
  const { login, resendVerificationEmail } = useAuth();
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [passwordVisible, setPasswordVisible] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [infoMsg, setInfoMsg] = useState('');

  const normalizedIdentifier = identifier.toLowerCase().trim();
  const looksLikeEmail = normalizedIdentifier.includes('@');
  const identifierIsValid = looksLikeEmail ? isValidEmail(normalizedIdentifier) : isValidUsername(normalizedIdentifier);

  const [idStatus, setIdStatus] = useState('idle');
  const [idChecked, setIdChecked] = useState(false);
  const [identifierBlurred, setIdentifierBlurred] = useState(false);
  const [idInvalidated, setIdInvalidated] = useState(false);
  // Tracks if user has ever gotten a confirmed result — never resets
  const hadConfirmedCheck = useRef(false);
  const lastConfirmedId = useRef('');
  const requestedNextPath = new URLSearchParams(location.search).get('next');
  const stateRedirectPath = typeof location.state?.from === 'string' ? location.state.from : '';
  const nextPath = (requestedNextPath && requestedNextPath.startsWith('/'))
    ? requestedNextPath
    : (stateRedirectPath && stateRedirectPath.startsWith('/'))
      ? stateRedirectPath
      : '';

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    if (params.get('expired') !== 'true') {
      return;
    }

    setInfoMsg('Your session has expired. Please log in again.');
    params.delete('expired');
    const next = params.toString();
    const nextUrl = `${location.pathname}${next ? `?${next}` : ''}`;
    window.history.replaceState({}, document.title, nextUrl);
  }, [location.pathname, location.search]);

  const handleIdentifierBlur = async () => {
    if (!identifier || identifier.length < 3 || !identifierIsValid) {
      setIdStatus('idle');
      setIdChecked(false);
      setIdInvalidated(false);
      return;
    }
    // Same as last confirmed value — restore green instantly, no API call needed
    if (hadConfirmedCheck.current && normalizedIdentifier === lastConfirmedId.current) {
      setIdStatus('exists');
      setIdChecked(true);
      setIdInvalidated(false);
      return;
    }
    // Different from what was confirmed — show red immediately while API checks
    if (hadConfirmedCheck.current) {
      setIdInvalidated(true);
    }
    setIdStatus('checking');
    setIdChecked(false);
    try {
      let res;
      if (looksLikeEmail) {
        res = await checkEmailAvailability(normalizedIdentifier);
      } else {
        res = await checkUsernameAvailability(normalizedIdentifier);
      }
      setIdStatus(res.exists ? 'exists' : 'missing');
      setIdChecked(true);
      hadConfirmedCheck.current = true;
      if (res.exists) lastConfirmedId.current = normalizedIdentifier;
      setIdInvalidated(false);
    } catch {
      setIdStatus('idle');
      setIdChecked(false);
    }
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setErrorMsg('');
    setInfoMsg('');

    try {
      const data = await login(identifier, password);

      trackEvents.signIn({
        identifier,
        user_id: data.user?.id,
        login_timestamp: new Date().toISOString(),
      });

      if (nextPath) {
        navigate(nextPath, { replace: true });
      } else {
        performSmartRedirect(data.user, navigate);
      }
    } catch (error) {
      const message = (error.message || '').toLowerCase();
      if (message.includes('verify your email')) {
        setErrorMsg('Your account is not verified yet. Check your inbox or resend the verification email below.');
      } else if (message.includes('invalid credentials')) {
        try {
          if (!looksLikeEmail) {
            setErrorMsg('Invalid username or password.');
            return;
          }
          const availability = await checkEmailAvailability(normalizedIdentifier);
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

  const handleResend = async () => {
    if (!looksLikeEmail || !isValidEmail(normalizedIdentifier)) {
      setErrorMsg('Enter the email address you used for signup to resend verification.');
      return;
    }
    setLoading(true);
    setErrorMsg('');
    try {
      const data = await resendVerificationEmail(normalizedIdentifier);
      setInfoMsg(
        data.delivery === 'manual'
          ? 'A new verification link was created. SMTP is not configured yet, so use the link returned by the backend response.'
          : 'Verification email sent again. Please check your inbox.'
      );
    } catch (error) {
      setErrorMsg(error.message || 'Unable to resend verification email.');
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

          {infoMsg && (
            <div className="mb-4 p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-700 text-sm text-center">
              {infoMsg}
            </div>
          )}

          <form onSubmit={handleLogin} className="space-y-5">
            <div>
              <label className="block text-sm font-medium mb-1 text-[var(--color-text-secondary)]">Email or Username</label>
              <div className="relative">
                <input
                  type="text"
                  value={identifier}
                  onChange={(e) => {
                    setIdentifier(e.target.value);
                    setIdStatus('idle');
                    setIdChecked(false);
                  }}
                  onFocus={() => setIdentifierBlurred(false)}
                  onBlur={() => { setIdentifierBlurred(true); handleIdentifierBlur(); }}
                  required
                  disabled={loading}
                  className={`w-full px-4 py-2 rounded-lg bg-[var(--color-input-bg)] border focus:outline-none focus:ring-2 transition pr-10 ${idChecked && idStatus === 'exists' ? 'border-green-500 focus:ring-green-500' :
                    (idChecked && idStatus === 'missing') || (identifierBlurred && identifier.length > 0 && !identifierIsValid) || (idInvalidated && identifierBlurred) ? 'border-red-500 focus:ring-red-500' :
                      'border-[var(--color-border)] focus:ring-[var(--color-primary)]'
                    }`}
                  placeholder="you@example.com or your.username"
                />
                <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center justify-center">
                  {idStatus === 'checking' && <FiLoader className="animate-spin text-blue-500" />}
                  {idChecked && idStatus === 'exists' && <FiCheck className="text-green-500" strokeWidth={3} size={20} title="Account exists" />}
                  {((idChecked && idStatus === 'missing') || (identifierBlurred && identifier.length > 0 && !identifierIsValid) || (idInvalidated && identifierBlurred)) && <FiX className="text-red-500" strokeWidth={3} size={20} title="Invalid or not found" />}
                </div>
              </div>
              {identifierBlurred && identifier.length > 0 && identifier.length < 3 ? (
                <p className="mt-2 flex items-center gap-1.5 text-sm text-red-500">
                  <span className="flex items-center justify-center w-5 h-5 rounded-full bg-red-500 text-white font-bold text-xs shrink-0">!</span>
                  Enter a valid email or a username with at least 3 valid characters..
                </p>
              ) : (idChecked && idStatus === 'missing') || (identifierBlurred && identifier.length >= 3 && !identifierIsValid) || (idInvalidated && identifierBlurred) ? (
                <p className="mt-2 flex items-center gap-1.5 text-sm text-red-500">
                  <span className="flex items-center justify-center w-5 h-5 rounded-full bg-red-500 text-white font-bold text-xs shrink-0">!</span>
                  Don't have an account? Create one.
                </p>
              ) : null}
            </div>

            <div>
              <label className="block text-sm font-medium mb-1 text-[var(--color-text-secondary)]">Password</label>
              <div className="relative">
                <input
                  type={passwordVisible ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    if (errorMsg.toLowerCase().includes('password')) setErrorMsg('');
                  }}
                  required
                  disabled={loading}
                  className={`w-full px-4 py-2 rounded-lg bg-[var(--color-input-bg)] border focus:outline-none focus:ring-2 transition pr-20 ${errorMsg.toLowerCase().includes('password') && password.length > 0 ? 'border-red-500 focus:ring-red-500' : 'border-[var(--color-border)] focus:ring-[var(--color-primary)]'
                    }`}
                  placeholder="Enter your password"
                />
                <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center justify-center gap-2">
                  {errorMsg.toLowerCase().includes('password') && password.length > 0 && <FiX className="text-red-500" strokeWidth={3} size={20} title="Invalid password" />}
                  <button
                    type="button"
                    onClick={() => setPasswordVisible((prev) => !prev)}
                    className="text-[var(--color-text-secondary)] hover:text-[var(--color-primary)] transition"
                  >
                    {passwordVisible ? <FiEyeOff size={20} /> : <FiEye size={20} />}
                  </button>
                </div>
              </div>
              <div className="mt-2 flex items-center justify-between text-sm">
                <Link to="/forgot-password" className="text-[var(--color-primary)] hover:underline">
                  Forgot password?
                </Link>
                <Link to="/forgot-username" className="text-[var(--color-primary)] hover:underline">
                  Forgot username?
                </Link>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading || !identifierIsValid || !password}
              className="w-full py-2.5 rounded-lg bg-[var(--color-primary)] text-white font-medium hover:opacity-90 transition disabled:opacity-50"
            >
              {loading ? 'Signing in...' : 'Login'}
            </button>
          </form>

          <button
            type="button"
            onClick={handleResend}
            disabled={loading}
            className="w-full mt-4 py-2.5 rounded-lg border border-[var(--color-border)] text-[var(--color-text-primary)] font-medium hover:bg-[var(--color-input-bg)] transition disabled:opacity-50"
          >
            Resend verification email
          </button>

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
