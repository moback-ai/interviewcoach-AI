import React, { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { FiEye, FiEyeOff } from 'react-icons/fi';
import Navbar from '../components/Navbar';
import signupReferenceIntro from '../assets/auth/signup-reference-intro.png';
import signupReferenceFinal from '../assets/auth/signup-reference-final.png';
import { useTheme } from '../hooks/useTheme';
import { useAuth } from '../contexts/AuthContext';
import { formatAuthError, isValidEmail, isValidUsername } from '../lib/authClient';
import { performSmartRedirect } from '../utils/smartRouting';
import { trackEvents } from '../services/mixpanel';
import { checkEmailAvailability, checkUsernameAvailability } from '../utils/emailAvailability';
import { buildLoginCoachState } from '../utils/authCoachNotice';

function Signup() {
  const navigate = useNavigate();
  useTheme();
  const { signup } = useAuth();
  const [fullName, setFullName] = useState('');
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [acceptedTerms, setAcceptedTerms] = useState(false);
  const [passwordVisible, setPasswordVisible] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [usernameStatus, setUsernameStatus] = useState('idle');
  const [emailStatus, setEmailStatus] = useState('idle');
  const [usernameBlurred, setUsernameBlurred] = useState(false);
  const shellRef = useRef(null);
  const motionFrameRef = useRef(null);
  const prefersReducedMotionRef = useRef(false);

  useEffect(() => {
    prefersReducedMotionRef.current = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    return () => {
      if (motionFrameRef.current) {
        window.cancelAnimationFrame(motionFrameRef.current);
      }
    };
  }, []);

  const applyBackgroundMotion = (offsetX, offsetY) => {
    const shell = shellRef.current;
    if (!shell) {
      return;
    }

    shell.style.setProperty('--auth-cinematic-shift-x', `${offsetX * 22}px`);
    shell.style.setProperty('--auth-cinematic-shift-y', `${offsetY * 16}px`);
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

  const isRealEmail = (value) => {
    if (!isValidEmail(value)) {
      return false;
    }

    const domain = value.split('@')[1]?.toLowerCase() || '';
    const parts = domain.split('.');
    if (parts.length < 2) {
      return false;
    }

    const tld = parts[parts.length - 1];
    if (tld.length < 2) {
      return false;
    }

    const popularBases = ['gmail', 'yahoo', 'hotmail', 'outlook'];
    for (const base of popularBases) {
      if (domain !== `${base}.com` && domain.startsWith(base) && domain.endsWith('.com')) {
        return false;
      }
    }

    return true;
  };

  const handleUsernameBlur = async () => {
    if (!username || username.length < 3 || !isValidUsername(username)) {
      setUsernameStatus('idle');
      return;
    }

    setUsernameStatus('checking');
    try {
      const result = await checkUsernameAvailability(username.toLowerCase().trim());
      if (result.error) {
        setUsernameStatus('error');
      } else {
        setUsernameStatus(result.available ? 'available' : 'taken');
      }
    } catch {
      setUsernameStatus('idle');
    }
  };

  const handleEmailBlur = async () => {
    if (!email || !isRealEmail(email)) {
      setEmailStatus(!email ? 'idle' : 'invalid');
      return;
    }

    setEmailStatus('checking');
    try {
      const result = await checkEmailAvailability(email.toLowerCase().trim());
      setEmailStatus(result.available ? 'available' : 'taken');
    } catch {
      setEmailStatus('idle');
    }
  };

  const handleSignup = async (event) => {
    event.preventDefault();
    setLoading(true);
    setErrorMsg('');

    try {
      const normalizedUsername = username.toLowerCase().trim();
      const normalizedEmail = email.toLowerCase().trim();
      const availability = await checkEmailAvailability(normalizedEmail);
      if (!availability.available) {
        throw new Error('This email is already registered. Please log in instead.');
      }

      const usernameAvailability = await checkUsernameAvailability(normalizedUsername);
      if (usernameAvailability.error) {
        throw new Error(usernameAvailability.error);
      }
      if (!usernameAvailability.available) {
        throw new Error('This username is already taken. Please choose another one.');
      }

      const data = await signup(normalizedUsername, email, password, fullName);

      trackEvents.signUp({
        email,
        user_id: data.user?.id,
        full_name: fullName.trim(),
        signup_timestamp: new Date().toISOString(),
      });

      if (data.verification_required) {
        navigate('/login', {
          replace: true,
          state: buildLoginCoachState({
            identifier: normalizedEmail,
            notice: {
              tone: 'success',
              title: 'Confirmation mail sent',
              message: data.delivery === 'manual'
                ? 'Your account is ready. Email delivery is not configured yet, so a direct confirmation link is available for you.'
                : `Your account is ready. We sent a confirmation email to ${normalizedEmail}. Verify it, then sign in from there.`,
              actionLabel: data.verification_link ? 'Open confirmation link' : '',
              actionHref: data.verification_link || '',
            },
          }),
        });
        return;
      }

      performSmartRedirect(data.user, navigate);
    } catch (error) {
      setErrorMsg(formatAuthError(error));
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Navbar />
      <div
        ref={shellRef}
        className="auth-cinematic-stage auth-cinematic-signup auth-reference-page px-4 py-8"
        onPointerMove={handleBackgroundPointerMove}
        onPointerLeave={handleBackgroundPointerLeave}
      >
        <div className="auth-cinematic-grid auth-cinematic-grid-bright" aria-hidden="true" />
        <div className="auth-cinematic-glow auth-cinematic-signup-glow-left" aria-hidden="true" />
        <div className="auth-cinematic-glow auth-cinematic-signup-glow-right" aria-hidden="true" />
        <div className="auth-cinematic-beam auth-cinematic-beam-left" aria-hidden="true" />
        <div className="auth-cinematic-beam auth-cinematic-beam-right" aria-hidden="true" />
        <div className="auth-cinematic-signup-bar" aria-hidden="true" />

        <div className="relative z-10 flex min-h-[calc(100vh-2rem)] items-center justify-center">
          <div className="auth-reference-shell auth-reference-shell-signup">
            <span className="auth-reference-kicker auth-reference-kicker-signup">Register now</span>

            <div className="auth-reference-stage auth-reference-stage-signup">
              <img src={signupReferenceIntro} alt="" className="auth-reference-layer auth-reference-layer-base" />
              <img src={signupReferenceFinal} alt="" className="auth-reference-layer auth-reference-layer-final" />

              <form onSubmit={handleSignup} className="auth-reference-form auth-reference-form-signup">
                <label htmlFor="auth-signup-username" className="sr-only">Username</label>
                <input
                  id="auth-signup-username"
                  type="text"
                  value={username}
                  onChange={(e) => {
                    setUsername(e.target.value);
                    setUsernameStatus('idle');
                  }}
                  onFocus={() => setUsernameBlurred(false)}
                  onBlur={() => {
                    setUsernameBlurred(true);
                    handleUsernameBlur();
                  }}
                  required
                  disabled={loading}
                  autoComplete="username"
                  className="auth-reference-input auth-reference-input-signup"
                  placeholder=""
                />

                <label htmlFor="auth-signup-fullname" className="sr-only">Full Name</label>
                <input
                  id="auth-signup-fullname"
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  required
                  disabled={loading}
                  autoComplete="name"
                  className="auth-reference-input auth-reference-input-signup"
                  placeholder=""
                />

                <label htmlFor="auth-signup-email" className="sr-only">Email</label>
                <input
                  id="auth-signup-email"
                  type="email"
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    setEmailStatus('idle');
                  }}
                  onBlur={handleEmailBlur}
                  required
                  disabled={loading}
                  autoComplete="email"
                  className="auth-reference-input auth-reference-input-signup auth-reference-input-signup-email"
                  placeholder=""
                />

                <div className="auth-reference-password-wrap auth-reference-password-wrap-signup">
                  <label htmlFor="auth-signup-password" className="sr-only">Password</label>
                  <input
                    id="auth-signup-password"
                    type={passwordVisible ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    minLength={8}
                    disabled={loading}
                    autoComplete="new-password"
                    className="auth-reference-input auth-reference-input-signup auth-reference-input-signup-password"
                    placeholder="Create your password"
                  />
                  <button
                    type="button"
                    onClick={() => setPasswordVisible((prev) => !prev)}
                    className="auth-reference-password-toggle auth-reference-password-toggle-light"
                    aria-label={passwordVisible ? 'Hide password' : 'Show password'}
                  >
                    {passwordVisible ? <FiEyeOff size={18} /> : <FiEye size={18} />}
                  </button>
                </div>

                <button
                  type="submit"
                  disabled={loading || !fullName.trim() || !isValidUsername(username) || !isValidEmail(email) || password.length < 8 || !acceptedTerms}
                  className="auth-reference-submit auth-reference-submit-signup"
                >
                  {loading ? 'Creating account...' : 'Sign Up'}
                </button>
              </form>
            </div>

            <div className="auth-reference-meta auth-reference-meta-light">
              {errorMsg && <div className="auth-reference-banner auth-reference-banner-light auth-reference-banner-error-light">{errorMsg}</div>}

              {!errorMsg && usernameBlurred && username && !isValidUsername(username) && (
                <p className="auth-reference-help auth-reference-help-light">
                  Use at least 3 characters. Letters, numbers, dots, underscores, and hyphens are allowed.
                </p>
              )}
              {!errorMsg && emailStatus === 'invalid' && (
                <p className="auth-reference-help auth-reference-help-light">
                  Enter a valid email address like `you@gmail.com`.
                </p>
              )}
              {!errorMsg && emailStatus === 'taken' && (
                <p className="auth-reference-help auth-reference-help-light">
                  This email is already registered. Log in instead.
                </p>
              )}
              {!errorMsg && usernameStatus === 'taken' && (
                <p className="auth-reference-help auth-reference-help-light">
                  That username is already taken. Please choose another one.
                </p>
              )}
              {!errorMsg && password.length > 0 && password.length < 8 && (
                <p className="auth-reference-help auth-reference-help-light">
                  Password must be at least 8 characters.
                </p>
              )}

              <label className="auth-reference-terms">
                <input
                  type="checkbox"
                  checked={acceptedTerms}
                  onChange={(e) => setAcceptedTerms(e.target.checked)}
                />
                <span>I agree to the Terms and Privacy Policy.</span>
              </label>

              <div className="auth-reference-link-row auth-reference-link-row-light">
                <Link to="/login" className="auth-reference-link auth-reference-link-light">
                  Already have an account? Login
                </Link>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

export default Signup;
