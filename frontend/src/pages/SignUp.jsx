import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { FiEye, FiEyeOff, FiCheck, FiX, FiInfo } from 'react-icons/fi';
import Navbar from '../components/Navbar';
import AuthStudioShell from '../components/auth/AuthStudioShell';
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
  const [passwordBlurred, setPasswordBlurred] = useState(false);

  const isRealEmail = (value) => {
    if (!isValidEmail(value)) return false;
    const domain = (value.split('@')[1] || '').toLowerCase();
    const parts = domain.split('.');
    if (parts.length < 2 || parts[parts.length - 1].length < 2) return false;
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

      if (!isRealEmail(normalizedEmail)) {
        throw new Error('Please enter a valid email address.');
      }

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
      <AuthStudioShell
        eyebrow="Create account"
        title="Start your practice account"
        description="Create an account to upload your resume and generate tailored interview questions."
        heroTitle="Join InterviewCoach."
        heroCopy="Build confidence with AI-powered mock interviews designed around your resume and the roles you want."
        wide
        footer={(
          <p className="auth-simple-footer-copy">
            Already have an account?{' '}
            <Link to="/login" className="auth-simple-link">
              Sign in
            </Link>
          </p>
        )}
      >
        {errorMsg ? (
          <div className="auth-simple-alert auth-simple-alert-error flex items-start gap-2" role="alert">
            <FiInfo className="w-4 h-4 shrink-0 mt-0.5 text-[var(--color-error)]" aria-hidden="true" />
            <p className="m-0">{errorMsg}</p>
          </div>
        ) : null}

        <form onSubmit={handleSignup} className="auth-simple-form">
          <div className="auth-simple-field">
            <label htmlFor="auth-signup-fullname" className="auth-simple-label">Full name</label>
            <input
              id="auth-signup-fullname"
              type="text"
              value={fullName}
              onChange={(e) => {
                setFullName(e.target.value);
                setErrorMsg('');
              }}
              required
              disabled={loading}
              autoComplete="name"
              className="auth-simple-input"
              placeholder="Your full name"
            />
          </div>

          <div className="auth-simple-field">
            <label htmlFor="auth-signup-username" className="auth-simple-label">Username</label>
            <input
              id="auth-signup-username"
              type="text"
              value={username}
              onChange={(e) => {
                setUsername(e.target.value);
                setUsernameStatus('idle');
                setErrorMsg('');
              }}
              onFocus={() => setUsernameBlurred(false)}
              onBlur={() => {
                setUsernameBlurred(true);
                handleUsernameBlur();
              }}
              required
              disabled={loading}
              autoComplete="username"
              className="auth-simple-input"
              placeholder="your.username"
            />
            {!errorMsg && usernameBlurred && username && !isValidUsername(username) ? (
              <p className="auth-simple-helper auth-simple-helper-error flex items-start gap-1.5">
                <FiInfo className="w-3.5 h-3.5 shrink-0 mt-0.5 text-[var(--color-error)]" aria-hidden="true" />
                <span>Use at least 3 characters. Letters, numbers, dots, underscores, and hyphens are allowed.</span>
              </p>
            ) : null}
            {!errorMsg && usernameStatus === 'taken' ? (
              <p className="auth-simple-helper auth-simple-helper-error flex items-start gap-1.5">
                <FiInfo className="w-3.5 h-3.5 shrink-0 mt-0.5 text-[var(--color-error)]" aria-hidden="true" />
                <span>That username is already taken. Please choose another one.</span>
              </p>
            ) : null}
            {!errorMsg && usernameStatus === 'error' ? (
              <p className="auth-simple-helper auth-simple-helper-error flex items-start gap-1.5">
                <FiInfo className="w-3.5 h-3.5 shrink-0 mt-0.5 text-[var(--color-error)]" aria-hidden="true" />
                <span>Could not check username availability. Please try again.</span>
              </p>
            ) : null}
          </div>

          <div className="auth-simple-field">
            <label htmlFor="auth-signup-email" className="auth-simple-label">Email</label>
            <div className="auth-simple-input-wrap">
              <input
                id="auth-signup-email"
                type="email"
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value);
                  setEmailStatus('idle');
                  setErrorMsg('');
                }}
                onBlur={handleEmailBlur}
                required
                disabled={loading}
                autoComplete="email"
                className={`auth-simple-input ${emailStatus !== 'idle' ? 'auth-simple-input-with-button' : ''} ${emailStatus === 'available' ? 'auth-simple-input-success' : emailStatus === 'taken' || emailStatus === 'invalid' ? 'auth-simple-input-error' : ''}`}
                placeholder="you@example.com"
              />
              {emailStatus !== 'idle' && (
                <div className="auth-simple-input-status-indicator">
                  {emailStatus === 'checking' && (
                    <div className="auth-scene-spinner" style={{ color: 'var(--color-primary)' }}>
                      <svg className="animate-spin" viewBox="0 0 24 24" fill="none" style={{ width: '1.25rem', height: '1.25rem' }}>
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                    </div>
                  )}
                  {emailStatus === 'available' && (
                    <FiCheck className="auth-simple-email-indicator-success" size={20} />
                  )}
                  {(emailStatus === 'taken' || emailStatus === 'invalid') && (
                    <FiX className="auth-simple-email-indicator-error" size={20} />
                  )}
                </div>
              )}
            </div>
            {!errorMsg && emailStatus === 'invalid' ? (
              <p className="auth-simple-helper auth-simple-helper-error flex items-start gap-1.5">
                <FiInfo className="w-3.5 h-3.5 shrink-0 mt-0.5 text-[var(--color-error)]" aria-hidden="true" />
                <span>Enter a valid email address (e.g. you@gmail.com or you@yahoo.com).</span>
              </p>
            ) : null}
            {!errorMsg && emailStatus === 'taken' ? (
              <p className="auth-simple-helper auth-simple-helper-error flex items-start gap-1.5">
                <FiInfo className="w-3.5 h-3.5 shrink-0 mt-0.5 text-[var(--color-error)]" aria-hidden="true" />
                <span>This email is already registered. Log in instead.</span>
              </p>
            ) : null}
          </div>

          <div className="auth-simple-field">
            <label htmlFor="auth-signup-password" className="auth-simple-label">Password</label>
            <div className="auth-simple-input-wrap">
              <input
                id="auth-signup-password"
                type={passwordVisible ? 'text' : 'password'}
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value);
                  setPasswordBlurred(false);
                  setErrorMsg('');
                }}
                onBlur={() => setPasswordBlurred(true)}
                required
                minLength={8}
                disabled={loading}
                autoComplete="new-password"
                className="auth-simple-input auth-simple-input-with-button"
                placeholder="At least 8 characters"
              />
              <button
                type="button"
                onClick={() => setPasswordVisible((prev) => !prev)}
                className="auth-simple-password-toggle"
                aria-label={passwordVisible ? 'Hide password' : 'Show password'}
              >
                {passwordVisible ? <FiEyeOff size={18} /> : <FiEye size={18} />}
              </button>
            </div>
            {!errorMsg && passwordBlurred && password.length > 0 && password.length < 8 ? (
              <p className="auth-simple-helper auth-simple-helper-error flex items-start gap-1.5">
                <FiInfo className="w-3.5 h-3.5 shrink-0 mt-0.5 text-[var(--color-error)]" aria-hidden="true" />
                <span>Password must be at least 8 characters.</span>
              </p>
            ) : null}
          </div>

          <label className="auth-simple-checkbox">
            <input
              type="checkbox"
              checked={acceptedTerms}
              onChange={(e) => setAcceptedTerms(e.target.checked)}
            />
            <span>I agree to the Terms and Privacy Policy.</span>
          </label>

          <button
            type="submit"
            disabled={loading || !fullName.trim() || !isValidUsername(username) || !isRealEmail(email) || password.length < 8 || !acceptedTerms}
            className={`auth-simple-submit ${(!loading && fullName.trim() && isValidUsername(username) && isRealEmail(email) && password.length > 0 && acceptedTerms) ? 'auth-simple-submit-valid' : ''}`}
          >
            {loading ? 'Creating account...' : 'Create account'}
          </button>
        </form>
      </AuthStudioShell>
    </>
  );
}

export default Signup;
