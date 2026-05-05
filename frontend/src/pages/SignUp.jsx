import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { FiEye, FiEyeOff, FiCheck, FiX, FiLoader } from 'react-icons/fi';
import { useEffect } from 'react';
import Navbar from '../components/Navbar';
import { useTheme } from '../hooks/useTheme';
import { useAuth } from '../contexts/AuthContext';
import { formatAuthError, isValidEmail, isValidUsername } from '../lib/authClient';
import { performSmartRedirect } from '../utils/smartRouting';
import { trackEvents } from '../services/mixpanel';
import { checkEmailAvailability, checkUsernameAvailability } from '../utils/emailAvailability';

function Signup() {
  const navigate = useNavigate();
  useTheme();
  const { signup, resendVerificationEmail } = useAuth();
  const [fullName, setFullName] = useState('');
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [acceptedTerms, setAcceptedTerms] = useState(false);
  const [passwordVisible, setPasswordVisible] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [successMsg, setSuccessMsg] = useState('');
  const [pendingEmail, setPendingEmail] = useState('');
  const [verificationLink, setVerificationLink] = useState('');
  const [usernameStatus, setUsernameStatus] = useState('idle');
  const [emailStatus, setEmailStatus] = useState('idle');
  const [usernameBlurred, setUsernameBlurred] = useState(false);

  const isRealEmail = (email) => {
    if (!isValidEmail(email)) return false;
    const domain = email.split('@')[1]?.toLowerCase() || '';
    // Must have a real TLD (at least 2 chars after the last dot) and a domain
    const parts = domain.split('.');
    if (parts.length < 2) return false;
    const tld = parts[parts.length - 1];
    if (tld.length < 2) return false;
    // Block obviously misspelled popular domains
    const knownDomains = ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'icloud.com', 'protonmail.com'];
    const popularBases = ['gmail', 'yahoo', 'hotmail', 'outlook'];
    for (const base of popularBases) {
      if (domain !== `${base}.com` && domain.startsWith(base) && domain.endsWith('.com')) {
        return false; // e.g. gamail.com, gmails.com
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
      const res = await checkUsernameAvailability(username.toLowerCase().trim());
      if (res.error) setUsernameStatus('error');
      else setUsernameStatus(res.available ? 'available' : 'taken');
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
      const res = await checkEmailAvailability(email.toLowerCase().trim());
      setEmailStatus(res.available ? 'available' : 'taken');
    } catch {
      setEmailStatus('idle');
    }
  };

  const handleSignup = async (e) => {
    e.preventDefault();
    setLoading(true);
    setErrorMsg('');
    setSuccessMsg('');
    setVerificationLink('');

    try {
      const normalizedUsername = username.toLowerCase().trim();
      const availability = await checkEmailAvailability(email.toLowerCase().trim());
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
        setPendingEmail(email.toLowerCase().trim());
        setVerificationLink(data.verification_link || '');
        setSuccessMsg(
          data.delivery === 'manual'
            ? 'Account created. SMTP is not configured yet, so use the verification link shown below.'
            : 'Account created. Check your email and verify your account before logging in.'
        );
        return;
      }

      performSmartRedirect(data.user, navigate);
    } catch (error) {
      setErrorMsg(formatAuthError(error));
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    setLoading(true);
    setErrorMsg('');
    try {
      const data = await resendVerificationEmail(pendingEmail || email);
      setVerificationLink(data.verification_link || '');
      setSuccessMsg(
        data.delivery === 'manual'
          ? 'A fresh verification link was created. SMTP is still not configured, so use the link below.'
          : 'Verification email sent again. Please check your inbox.'
      );
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

          {successMsg && (
            <div className="mb-4 p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-700 text-sm text-center">
              {successMsg}
            </div>
          )}

          {verificationLink && (
            <div className="mb-4 p-3 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 text-sm break-all">
              <p className="font-medium mb-1">Verification link</p>
              <a href={verificationLink} className="underline hover:opacity-80">
                {verificationLink}
              </a>
            </div>
          )}

          <form onSubmit={handleSignup} className="space-y-5">
            <div>
              <label className="block text-sm font-medium mb-1 text-[var(--color-text-secondary)]">Username</label>
              <div className="relative">
                <input
                  type="text"
                  value={username}
                  onChange={(e) => { setUsername(e.target.value); setUsernameStatus('idle'); }}
                  onFocus={() => setUsernameBlurred(false)}
                  onBlur={() => { setUsernameBlurred(true); handleUsernameBlur(); }}
                  required
                  disabled={loading}
                  className={`w-full px-4 py-2 rounded-lg bg-[var(--color-input-bg)] border focus:outline-none focus:ring-2 transition pr-10 ${usernameStatus === 'available' ? 'border-green-500 focus:ring-green-500' :
                      (usernameStatus === 'taken' || usernameStatus === 'error') ? 'border-red-500 focus:ring-red-500' :
                        'border-[var(--color-border)] focus:ring-[var(--color-primary)]'
                    }`}
                  placeholder="your.username"
                />
                <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center justify-center">
                  {usernameStatus === 'checking' && <FiLoader className="animate-spin text-blue-500" />}
                  {usernameStatus === 'available' && <FiCheck className="text-green-500" strokeWidth={3} size={20} title="Username available" />}
                  {(usernameStatus === 'taken' || usernameStatus === 'error') && <FiX className="text-red-500" strokeWidth={3} size={20} title="Username taken or invalid" />}
                </div>
              </div>
              {usernameBlurred && username && !isValidUsername(username) && (
                <p className="text-xs text-red-500 mt-1">Use at least 3 characters. Letters, numbers, dots, underscores, and hyphens are allowed.</p>
              )}
            </div>

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
              <div className="relative">
                <input
                  type="email"
                  value={email}
                  onChange={(e) => { setEmail(e.target.value); setEmailStatus('idle'); }}
                  onBlur={handleEmailBlur}
                  required
                  disabled={loading}
                  className={`w-full px-4 py-2 rounded-lg bg-[var(--color-input-bg)] border focus:outline-none focus:ring-2 transition pr-10 ${emailStatus === 'available' ? 'border-green-500 focus:ring-green-500' :
                      (emailStatus === 'taken' || emailStatus === 'invalid') ? 'border-red-500 focus:ring-red-500' :
                        'border-[var(--color-border)] focus:ring-[var(--color-primary)]'
                    }`}
                  placeholder="you@example.com"
                />
                <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center justify-center">
                  {emailStatus === 'checking' && <FiLoader className="animate-spin text-blue-500" />}
                  {emailStatus === 'available' && <FiCheck className="text-green-500" strokeWidth={3} size={20} title="Email available" />}
                  {(emailStatus === 'taken' || emailStatus === 'invalid') && <FiX className="text-red-500" strokeWidth={3} size={20} title="Invalid or already registered" />}
                </div>
              </div>
              {emailStatus === 'invalid' && (
                <p className="text-xs text-red-500 mt-1">Enter a valid email address (e.g. you@gmail.com).</p>
              )}
              {emailStatus === 'taken' && (
                <p className="mt-2 flex items-center gap-1.5 text-sm text-red-500">
                  <span className="flex items-center justify-center w-5 h-5 rounded-full bg-red-500 text-white font-bold text-xs shrink-0">!</span>
                  Email already registered, login instead.
                </p>
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
                  minLength={8}
                  disabled={loading}
                  className={`w-full px-4 py-2 rounded-lg bg-[var(--color-input-bg)] border focus:outline-none focus:ring-2 transition pr-20 ${password.length >= 8 ? 'border-green-500 focus:ring-green-500' :
                      password.length > 0 ? 'border-red-500 focus:ring-red-500' :
                        'border-[var(--color-border)] focus:ring-[var(--color-primary)]'
                    }`}
                  placeholder="At least 8 characters"
                />
                <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center justify-center gap-2">
                  {password.length >= 8 && <FiCheck className="text-green-500" strokeWidth={3} size={20} title="Password meets requirements" />}
                  {password.length > 0 && password.length < 8 && <FiX className="text-red-500" strokeWidth={3} size={20} title="Password too short" />}
                  <button
                    type="button"
                    onClick={() => setPasswordVisible((prev) => !prev)}
                    className="text-[var(--color-text-secondary)] hover:text-[var(--color-primary)] transition"
                  >
                    {passwordVisible ? <FiEyeOff size={20} /> : <FiEye size={20} />}
                  </button>
                </div>
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
              disabled={loading || !fullName.trim() || !isValidUsername(username) || !isValidEmail(email) || password.length < 8 || !acceptedTerms}
              className="w-full py-2.5 rounded-lg bg-[var(--color-primary)] text-white font-medium hover:opacity-90 transition disabled:opacity-50"
            >
              {loading ? 'Creating account...' : 'Sign Up'}
            </button>
          </form>

          {!!pendingEmail && (
            <button
              type="button"
              onClick={handleResend}
              disabled={loading}
              className="w-full mt-4 py-2.5 rounded-lg border border-[var(--color-border)] text-[var(--color-text-primary)] font-medium hover:bg-[var(--color-input-bg)] transition disabled:opacity-50"
            >
              Resend verification email
            </button>
          )}

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
