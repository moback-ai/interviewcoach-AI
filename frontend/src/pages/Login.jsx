import React, { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import {
  FiArrowRight,
  FiCheckCircle,
  FiEye,
  FiEyeOff,
  FiInfo,
  FiMail,
  FiX,
  FiCheck,
} from 'react-icons/fi';
import Navbar from '../components/Navbar';
import AuthStudioShell from '../components/auth/AuthStudioShell';
import { useTheme } from '../hooks/useTheme';
import { useAuth } from '../contexts/AuthContext';
import { isValidEmail, isValidUsername } from '../lib/authClient';
import { performSmartRedirect } from '../utils/smartRouting';
import { trackEvents } from '../services/mixpanel';
import { checkEmailAvailability } from '../utils/emailAvailability';
import { createAuthCoachNotice, getDefaultLoginCoachNotice } from '../utils/authCoachNotice';

const NOTICE_META = {
  success: {
    label: 'Ready',
    Icon: FiCheckCircle,
    panelClass: 'auth-simple-alert-success',
  },
  warning: {
    label: 'Action needed',
    Icon: FiMail,
    panelClass: 'auth-simple-alert-warning',
  },
  info: {
    label: 'Secure access',
    Icon: FiInfo,
    panelClass: 'auth-simple-alert-info',
  },
};

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
  const [coachNotice, setCoachNotice] = useState(() => getDefaultLoginCoachNotice());
  const [emailStatus, setEmailStatus] = useState('idle');
  const [identifierBlurred, setIdentifierBlurred] = useState(false);
  const [passwordBlurred, setPasswordBlurred] = useState(false);

  const normalizedIdentifier = identifier.toLowerCase().trim();
  const looksLikeEmail = normalizedIdentifier.includes('@');
  const identifierIsValid = looksLikeEmail ? isValidEmail(normalizedIdentifier) : isValidUsername(normalizedIdentifier);

  const handleIdentifierBlur = async () => {
    setIdentifierBlurred(true);
    if (!normalizedIdentifier) {
      setEmailStatus('idle');
      return;
    }

    if (looksLikeEmail) {
      if (!isValidEmail(normalizedIdentifier)) {
        setEmailStatus('invalid');
        return;
      }

      setEmailStatus('checking');
      try {
        const result = await checkEmailAvailability(normalizedIdentifier);
        setEmailStatus(!result.available ? 'exists' : 'not-exists');
      } catch {
        setEmailStatus('idle');
      }
    } else {
      setEmailStatus('idle');
    }
  };

  const requestedNextPath = new URLSearchParams(location.search).get('next');
  const stateRedirectPath = typeof location.state?.from === 'string' ? location.state.from : '';
  const nextPath = (requestedNextPath && requestedNextPath.startsWith('/'))
    ? requestedNextPath
    : (stateRedirectPath && stateRedirectPath.startsWith('/'))
      ? stateRedirectPath
      : '';

  const noticeMeta = NOTICE_META[coachNotice.tone] || NOTICE_META.info;
  const NoticeIcon = noticeMeta.Icon;

  useEffect(() => {
    const incomingNotice = location.state?.authNotice;
    const incomingIdentifier = typeof location.state?.prefillIdentifier === 'string'
      ? location.state.prefillIdentifier
      : '';

    if (!incomingNotice?.message && !incomingIdentifier) {
      return;
    }

    if (incomingIdentifier) {
      setIdentifier((currentValue) => currentValue || incomingIdentifier);
    }

    if (incomingNotice?.message) {
      setCoachNotice(incomingNotice);
      setErrorMsg('');
    }

    const nextState = typeof location.state?.from === 'string'
      ? { from: location.state.from }
      : null;

    navigate(
      {
        pathname: location.pathname,
        search: location.search,
      },
      {
        replace: true,
        state: nextState,
      }
    );
  }, [location.pathname, location.search, location.state, navigate]);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    if (params.get('expired') !== 'true') {
      return;
    }

    setCoachNotice(createAuthCoachNotice({
      tone: 'warning',
      title: 'Session expired',
      message: 'Your session has expired. Please log in again.',
    }));
    setErrorMsg('');

    params.delete('expired');
    const search = params.toString();

    navigate(
      {
        pathname: location.pathname,
        search: search ? `?${search}` : '',
      },
      {
        replace: true,
        state: location.state ?? null,
      }
    );
  }, [location.pathname, location.search, location.state, navigate]);

  const handleLogin = async (event) => {
    event.preventDefault();
    setLoading(true);
    setErrorMsg('');

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
        setCoachNotice(createAuthCoachNotice({
          tone: 'warning',
          title: 'Verification required',
          message: 'Your account needs a confirmed email before sign-in. Resend the verification email and then come right back here.',
        }));
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
      setCoachNotice(createAuthCoachNotice({
        tone: 'success',
        title: 'Confirmation mail sent',
        message: data.delivery === 'manual'
          ? 'A fresh confirmation link is ready. Email delivery is not configured yet, so use the direct link below to verify now.'
          : `A fresh confirmation email was sent to ${normalizedIdentifier}. Check your inbox and spam folder, then sign in here.`,
        actionLabel: data.verification_link ? 'Open confirmation link' : '',
        actionHref: data.verification_link || '',
      }));
    } catch (error) {
      setErrorMsg(error.message || 'Unable to resend verification email.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Navbar />
      <AuthStudioShell
        eyebrow="Sign in"
        title="Welcome back"
        description="Use your email or username and password to continue to your interview workspace."
        heroTitle="Your AI interview studio."
        heroCopy="Mock interviews tailored to your resume and target role — with voice practice and instant feedback."
        footer={(
          <>
            <p className="auth-simple-footer-copy">
              Don&apos;t have an account?{' '}
              <Link to="/signup" className="auth-simple-link">
                Create one
              </Link>
            </p>
            {import.meta.env.DEV ? (
              <p className="auth-simple-footer-copy" style={{ marginTop: '0.65rem' }}>
                <Link to="/style-lab/backgrounds" className="auth-simple-link">
                  Compare background styles →
                </Link>
              </p>
            ) : null}
          </>
        )}
      >
        {errorMsg ? (
          <div className="auth-simple-alert auth-simple-alert-error">
            <p>{errorMsg}</p>
          </div>
        ) : null}

        {!errorMsg && coachNotice.kind !== 'default' ? (
          <div className={`auth-simple-alert ${noticeMeta.panelClass}`}>
            <div className="auth-simple-alert-top">
              <span className="auth-simple-alert-chip">
                <NoticeIcon size={14} />
                {noticeMeta.label}
              </span>
              <button
                type="button"
                onClick={() => setCoachNotice(getDefaultLoginCoachNotice())}
                className="auth-simple-alert-close"
                aria-label="Dismiss sign-in notice"
              >
                <FiX size={14} />
              </button>
            </div>
            {coachNotice.title ? <p className="auth-simple-alert-title">{coachNotice.title}</p> : null}
            <p className="auth-simple-alert-body">{coachNotice.message}</p>
            {coachNotice.actionHref && coachNotice.actionLabel ? (
              <a href={coachNotice.actionHref} className="auth-simple-alert-link">
                <span>{coachNotice.actionLabel}</span>
                <FiArrowRight size={15} />
              </a>
            ) : null}
          </div>
        ) : null}

        <form onSubmit={handleLogin} className="auth-simple-form">
          <div className="auth-simple-field">
            <label htmlFor="auth-login-identifier" className="auth-simple-label">Email or Username</label>
            <div className="auth-simple-input-wrap">
              <input
                id="auth-login-identifier"
                type="text"
                value={identifier}
                onChange={(e) => {
                  setIdentifier(e.target.value);
                  setEmailStatus('idle');
                  setIdentifierBlurred(false);
                  setErrorMsg('');
                }}
                onBlur={handleIdentifierBlur}
                required
                disabled={loading}
                autoComplete="username"
                className={`auth-simple-input ${looksLikeEmail && emailStatus !== 'idle' ? 'auth-simple-input-with-button' : ''} ${looksLikeEmail && emailStatus === 'exists' ? 'auth-simple-input-success' : ((looksLikeEmail && identifierBlurred && (emailStatus === 'not-exists' || emailStatus === 'invalid')) || (!looksLikeEmail && identifierBlurred && identifier && !identifierIsValid)) ? 'auth-simple-input-error' : ''}`}
                placeholder="you@example.com or your.username"
              />
              {looksLikeEmail && emailStatus !== 'idle' && (
                <div className="auth-simple-input-status-indicator">
                  {emailStatus === 'checking' && (
                    <div className="auth-scene-spinner" style={{ color: 'var(--color-primary)' }}>
                      <svg className="animate-spin" viewBox="0 0 24 24" fill="none" style={{ width: '1.25rem', height: '1.25rem' }}>
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                    </div>
                  )}
                  {emailStatus === 'exists' && (
                    <FiCheck className="auth-simple-email-indicator-success" size={20} />
                  )}
                  {identifierBlurred && (emailStatus === 'not-exists' || emailStatus === 'invalid') && (
                    <FiX className="auth-simple-email-indicator-error" size={20} />
                  )}
                </div>
              )}
            </div>
            {!errorMsg && looksLikeEmail && identifierBlurred && emailStatus === 'invalid' ? (
              <p className="auth-simple-helper auth-simple-helper-error">
                Enter a valid email address.
              </p>
            ) : null}
            {!errorMsg && looksLikeEmail && identifierBlurred && emailStatus === 'not-exists' ? (
              <p className="auth-simple-helper auth-simple-helper-error">
                This email is not registered. Please sign up first.
              </p>
            ) : null}
            {!errorMsg && (!looksLikeEmail || emailStatus === 'idle') && identifier && identifierBlurred && !identifierIsValid ? (
              <p className="auth-simple-helper auth-simple-helper-error">
                Enter a valid email or a username with at least 3 characters.
              </p>
            ) : null}
          </div>

          <div className="auth-simple-field">
            <label htmlFor="auth-login-password" className="auth-simple-label">Password</label>
            <div className="auth-simple-input-wrap">
              <input
                id="auth-login-password"
                type={passwordVisible ? 'text' : 'password'}
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value);
                  setPasswordBlurred(false);
                  setErrorMsg('');
                }}
                onBlur={() => setPasswordBlurred(true)}
                required
                disabled={loading}
                autoComplete="current-password"
                className={`auth-simple-input ${password.length > 0 ? 'auth-simple-input-with-double-buttons' : 'auth-simple-input-with-button'} ${password.length >= 8 ? 'auth-simple-input-success' : (passwordBlurred && password.length > 0 && password.length < 8) ? 'auth-simple-input-error' : ''}`}
                placeholder="Enter your password"
              />
              {password.length > 0 && (
                <div className="auth-simple-input-status-indicator-double">
                  {password.length >= 8 ? (
                    <FiCheck className="auth-simple-email-indicator-success" size={20} />
                  ) : passwordBlurred ? (
                    <FiX className="auth-simple-email-indicator-error" size={20} />
                  ) : null}
                </div>
              )}
              <button
                type="button"
                onClick={() => setPasswordVisible((prev) => !prev)}
                className="auth-simple-password-toggle"
                aria-label={passwordVisible ? 'Hide password' : 'Show password'}
              >
                {passwordVisible ? <FiEyeOff size={18} /> : <FiEye size={18} />}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading || !identifierIsValid || !password}
            className={`auth-simple-submit ${(!loading && identifierIsValid && password.length >= 8) ? 'auth-simple-submit-valid' : ''}`}
          >
            {loading ? 'Signing in...' : 'Sign in'}
          </button>
        </form>

        <div className="auth-simple-link-grid">
          <Link to="/forgot-password" className="auth-simple-link">
            Forgot password?
          </Link>
          <Link to="/forgot-username" className="auth-simple-link">
            Forgot username?
          </Link>
          <button
            type="button"
            onClick={handleResend}
            disabled={loading}
            className="auth-simple-link auth-simple-link-button"
          >
            Resend verification
          </button>
        </div>
      </AuthStudioShell>
    </>
  );
}

export default Login;
