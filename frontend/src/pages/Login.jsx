import React, { useEffect, useRef, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import {
  FiArrowRight,
  FiCheckCircle,
  FiEye,
  FiEyeOff,
  FiInfo,
  FiMail,
  FiX,
} from 'react-icons/fi';
import Navbar from '../components/Navbar';
import loginReferenceEmpty from '../assets/auth/login-reference-empty.png';
import loginReferenceFinal from '../assets/auth/login-reference-final.png';
import { useTheme } from '../hooks/useTheme';
import { useAuth } from '../contexts/AuthContext';
import { isValidEmail, isValidUsername } from '../lib/authClient';
import { performSmartRedirect } from '../utils/smartRouting';
import { trackEvents } from '../services/mixpanel';
import { checkEmailAvailability, checkUsernameAvailability } from '../utils/emailAvailability';
import { createAuthCoachNotice, getDefaultLoginCoachNotice } from '../utils/authCoachNotice';

const NOTICE_META = {
  success: {
    label: 'Ready',
    Icon: FiCheckCircle,
    panelClass: 'auth-cinematic-note-success',
  },
  warning: {
    label: 'Action needed',
    Icon: FiMail,
    panelClass: 'auth-cinematic-note-warning',
  },
  info: {
    label: 'Secure access',
    Icon: FiInfo,
    panelClass: 'auth-cinematic-note-info',
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

  const normalizedIdentifier = identifier.toLowerCase().trim();
  const looksLikeEmail = normalizedIdentifier.includes('@');
  const identifierIsValid = looksLikeEmail ? isValidEmail(normalizedIdentifier) : isValidUsername(normalizedIdentifier);

  const [idStatus, setIdStatus] = useState('idle');
  const [idChecked, setIdChecked] = useState(false);
  const [identifierBlurred, setIdentifierBlurred] = useState(false);
  const [idInvalidated, setIdInvalidated] = useState(false);
  const hadConfirmedCheck = useRef(false);
  const lastConfirmedId = useRef('');
  const shellRef = useRef(null);
  const motionFrameRef = useRef(null);
  const prefersReducedMotionRef = useRef(false);

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
    prefersReducedMotionRef.current = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    return () => {
      if (motionFrameRef.current) {
        window.cancelAnimationFrame(motionFrameRef.current);
      }
    };
  }, []);

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

  const applyBackgroundMotion = (offsetX, offsetY) => {
    const shell = shellRef.current;
    if (!shell) {
      return;
    }

    shell.style.setProperty('--auth-cinematic-shift-x', `${offsetX * 26}px`);
    shell.style.setProperty('--auth-cinematic-shift-y', `${offsetY * 18}px`);
    shell.style.setProperty('--auth-cinematic-frame-x', `${offsetX * -14}px`);
    shell.style.setProperty('--auth-cinematic-frame-y', `${offsetY * 10}px`);
    shell.style.setProperty('--auth-cinematic-rotate', `${offsetX * 4}deg`);
  };

  const queueBackgroundMotion = (offsetX, offsetY) => {
    if (prefersReducedMotionRef.current) {
      return;
    }

    if (motionFrameRef.current) {
      window.cancelAnimationFrame(motionFrameRef.current);
    }

    motionFrameRef.current = window.requestAnimationFrame(() => {
      applyBackgroundMotion(offsetX, offsetY);
      motionFrameRef.current = null;
    });
  };

  const handleBackgroundPointerMove = (event) => {
    if (event.pointerType === 'touch' || prefersReducedMotionRef.current) {
      return;
    }

    const shell = shellRef.current;
    if (!shell) {
      return;
    }

    const bounds = shell.getBoundingClientRect();
    const relativeX = ((event.clientX - bounds.left) / bounds.width - 0.5) * 2;
    const relativeY = ((event.clientY - bounds.top) / bounds.height - 0.5) * 2;
    queueBackgroundMotion(relativeX, relativeY);
  };

  const handleBackgroundPointerLeave = () => {
    queueBackgroundMotion(0, 0);
  };

  const handleIdentifierBlur = async () => {
    if (!identifier || identifier.length < 3 || !identifierIsValid) {
      setIdStatus('idle');
      setIdChecked(false);
      setIdInvalidated(false);
      return;
    }

    if (hadConfirmedCheck.current && normalizedIdentifier === lastConfirmedId.current) {
      setIdStatus('exists');
      setIdChecked(true);
      setIdInvalidated(false);
      return;
    }

    if (hadConfirmedCheck.current) {
      setIdInvalidated(true);
    }

    setIdStatus('checking');
    setIdChecked(false);
    try {
      const result = looksLikeEmail
        ? await checkEmailAvailability(normalizedIdentifier)
        : await checkUsernameAvailability(normalizedIdentifier);

      setIdStatus(result.exists ? 'exists' : 'missing');
      setIdChecked(true);
      hadConfirmedCheck.current = true;
      if (result.exists) {
        lastConfirmedId.current = normalizedIdentifier;
      }
      setIdInvalidated(false);
    } catch {
      setIdStatus('idle');
      setIdChecked(false);
    }
  };

  const handleLogin = async (event) => {
    event.preventDefault();
    setLoading(true);
    setErrorMsg('');
    let redirecting = false;

    try {
      const data = await login(identifier, password);

      trackEvents.signIn({
        identifier,
        user_id: data.user?.id,
        login_timestamp: new Date().toISOString(),
      });

      redirecting = true;
      setCoachNotice(createAuthCoachNotice({
        tone: 'success',
        title: 'Signing successful',
        message: `Welcome back${data.user?.user_metadata?.full_name ? `, ${data.user.user_metadata.full_name.split(' ')[0]}` : ''}. Opening your interview workspace now.`,
      }));

      await new Promise((resolve) => {
        window.setTimeout(resolve, 900);
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
      if (!redirecting) {
        setLoading(false);
      }
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
      <div
        ref={shellRef}
        className="auth-cinematic-stage auth-cinematic-login auth-reference-page px-4 py-8"
        onPointerMove={handleBackgroundPointerMove}
        onPointerLeave={handleBackgroundPointerLeave}
      >
        <div className="auth-cinematic-grid" aria-hidden="true" />
        <div className="auth-cinematic-glow auth-cinematic-glow-left" aria-hidden="true" />
        <div className="auth-cinematic-glow auth-cinematic-glow-right" aria-hidden="true" />
        <div className="auth-cinematic-beam auth-cinematic-beam-left" aria-hidden="true" />
        <div className="auth-cinematic-beam auth-cinematic-beam-right" aria-hidden="true" />
        <div className="auth-cinematic-frame-shell" aria-hidden="true">
          <div className="auth-cinematic-frame" />
        </div>

        <div className="relative z-10 flex min-h-[calc(100vh-2rem)] items-center justify-center">
          <div className="auth-reference-shell auth-reference-shell-login">
            <span className="auth-reference-kicker auth-reference-kicker-login">Studio access</span>

            <div className="auth-reference-stage auth-reference-stage-login">
              <img src={loginReferenceEmpty} alt="" className="auth-reference-layer auth-reference-layer-base" />
              <img src={loginReferenceFinal} alt="" className="auth-reference-layer auth-reference-layer-final" />

              <form onSubmit={handleLogin} className="auth-reference-form auth-reference-form-login">
                <label htmlFor="auth-login-identifier" className="sr-only">Email or Username</label>
                <input
                  id="auth-login-identifier"
                  type="text"
                  value={identifier}
                  onChange={(e) => {
                    setIdentifier(e.target.value);
                    setIdStatus('idle');
                    setIdChecked(false);
                  }}
                  onFocus={() => setIdentifierBlurred(false)}
                  onBlur={() => {
                    setIdentifierBlurred(true);
                    handleIdentifierBlur();
                  }}
                  required
                  disabled={loading}
                  autoComplete="username"
                  className="auth-reference-input auth-reference-input-login"
                  placeholder=""
                />

                <div className="auth-reference-password-wrap auth-reference-password-wrap-login">
                  <label htmlFor="auth-login-password" className="sr-only">Password</label>
                  <input
                    id="auth-login-password"
                    type={passwordVisible ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => {
                      setPassword(e.target.value);
                      if (errorMsg.toLowerCase().includes('password')) {
                        setErrorMsg('');
                      }
                    }}
                    required
                    disabled={loading}
                    autoComplete="current-password"
                    className="auth-reference-input auth-reference-input-login auth-reference-input-password"
                    placeholder=""
                  />
                  <button
                    type="button"
                    onClick={() => setPasswordVisible((prev) => !prev)}
                    className="auth-reference-password-toggle"
                    aria-label={passwordVisible ? 'Hide password' : 'Show password'}
                  >
                    {passwordVisible ? <FiEyeOff size={18} /> : <FiEye size={18} />}
                  </button>
                </div>

                <button
                  type="submit"
                  disabled={loading || !identifierIsValid || !password}
                  className="auth-reference-submit auth-reference-submit-login"
                >
                  {loading ? 'Signing in...' : <span className="sr-only">Login</span>}
                </button>
              </form>
            </div>

            <div className="auth-reference-meta">
              {errorMsg && <div className="auth-reference-banner auth-reference-banner-error">{errorMsg}</div>}

              {!errorMsg && coachNotice.kind !== 'default' && (
                <div className={`auth-reference-banner ${noticeMeta.panelClass}`}>
                  <div className="auth-reference-banner-top">
                    <span className="auth-reference-banner-chip">
                      <NoticeIcon size={14} />
                      {noticeMeta.label}
                    </span>
                    <button
                      type="button"
                      onClick={() => setCoachNotice(getDefaultLoginCoachNotice())}
                      className="auth-reference-banner-close"
                      aria-label="Dismiss sign-in notice"
                    >
                      <FiX size={14} />
                    </button>
                  </div>
                  {coachNotice.title && <p className="auth-reference-banner-title">{coachNotice.title}</p>}
                  <p className="auth-reference-banner-body">{coachNotice.message}</p>
                  {coachNotice.actionHref && coachNotice.actionLabel && (
                    <a href={coachNotice.actionHref} className="auth-reference-banner-link">
                      <span>{coachNotice.actionLabel}</span>
                      <FiArrowRight size={15} />
                    </a>
                  )}
                </div>
              )}

              {identifierBlurred && identifier.length > 0 && identifier.length < 3 && (
                <p className="auth-reference-help">Enter a valid email or a username with at least 3 characters.</p>
              )}
              {!errorMsg && ((idChecked && idStatus === 'missing') || (identifierBlurred && identifier.length >= 3 && !identifierIsValid) || (idInvalidated && identifierBlurred)) && (
                <p className="auth-reference-help">This account wasn&apos;t found. You can create one below.</p>
              )}

              <div className="auth-reference-link-row">
                <Link to="/forgot-password" className="auth-reference-link auth-reference-link-dark">
                  Forgot password?
                </Link>
                <Link to="/forgot-username" className="auth-reference-link auth-reference-link-dark">
                  Forgot username?
                </Link>
                <button
                  type="button"
                  onClick={handleResend}
                  disabled={loading}
                  className="auth-reference-link auth-reference-link-dark auth-reference-link-button"
                >
                  Resend verification
                </button>
                <Link to="/signup" className="auth-reference-link auth-reference-link-dark">
                  Create account
                </Link>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

export default Login;
