import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { FiEye, FiEyeOff } from 'react-icons/fi';
import Navbar from '../components/Navbar';
import AuthSimpleShell from '../components/auth/AuthSimpleShell';
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
      <AuthSimpleShell
        eyebrow="Create account"
        title="Start your practice account"
        description="Create a simple account to upload your resume, tailor interview questions, and track your mock interview progress."
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
          <div className="auth-simple-alert auth-simple-alert-error">
            <p>{errorMsg}</p>
          </div>
        ) : null}

        <form onSubmit={handleSignup} className="auth-simple-form">
          <div className="auth-simple-field">
            <label htmlFor="auth-signup-fullname" className="auth-simple-label">Full name</label>
            <input
              id="auth-signup-fullname"
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
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
              <p className="auth-simple-helper auth-simple-helper-error">
                Use at least 3 characters. Letters, numbers, dots, underscores, and hyphens are allowed.
              </p>
            ) : null}
            {!errorMsg && usernameStatus === 'taken' ? (
              <p className="auth-simple-helper auth-simple-helper-error">
                That username is already taken. Please choose another one.
              </p>
            ) : null}
          </div>

          <div className="auth-simple-field">
            <label htmlFor="auth-signup-email" className="auth-simple-label">Email</label>
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
              className="auth-simple-input"
              placeholder="you@example.com"
            />
            {!errorMsg && emailStatus === 'invalid' ? (
              <p className="auth-simple-helper auth-simple-helper-error">
                Enter a valid email address like `you@gmail.com`.
              </p>
            ) : null}
            {!errorMsg && emailStatus === 'taken' ? (
              <p className="auth-simple-helper auth-simple-helper-error">
                This email is already registered. Log in instead.
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
                onChange={(e) => setPassword(e.target.value)}
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
            {!errorMsg && password.length > 0 && password.length < 8 ? (
              <p className="auth-simple-helper auth-simple-helper-error">
                Password must be at least 8 characters.
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
            disabled={loading || !fullName.trim() || !isValidUsername(username) || !isValidEmail(email) || password.length < 8 || !acceptedTerms}
            className="auth-simple-submit"
          >
            {loading ? 'Creating account...' : 'Create account'}
          </button>
        </form>
      </AuthSimpleShell>
    </>
  );
}

export default Signup;
