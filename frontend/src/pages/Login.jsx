import React, { useState, useRef, useEffect } from 'react';
import { supabase } from '../supabaseClient';
import { useNavigate, Link } from 'react-router-dom';
import { useTheme } from '../hooks/useTheme';
import { FiEye, FiEyeOff, FiMail, FiCheckCircle, FiAlertCircle, FiLoader } from 'react-icons/fi';
import Navbar from '../components/Navbar';
import { performSmartRedirect } from '../utils/smartRouting';
import { trackEvents } from '../services/mixpanel';
import { checkEmailAvailability } from '../utils/emailAvailability';
import { isValidEmail } from '../utils/emailVerificationUtils';

function Login() {
  const navigate = useNavigate();
  const { theme } = useTheme();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [passwordVisible, setPasswordVisible] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [successMsg, setSuccessMsg] = useState('');
  const [loading, setLoading] = useState(false);
  const [showForgotPassword, setShowForgotPassword] = useState(false);
  const [resetEmailSent, setResetEmailSent] = useState(false);
  
  // Email validation states
  const [emailChecking, setEmailChecking] = useState(false);
  const [emailExists, setEmailExists] = useState(null); // null = not checked, true = exists, false = doesn't exist
  const [emailTouched, setEmailTouched] = useState(false);
  const emailCheckTimeoutRef = useRef(null);

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (emailCheckTimeoutRef.current) {
        clearTimeout(emailCheckTimeoutRef.current);
      }
    };
  }, []);

  // Handle email input change with debouncing
  const handleEmailChange = (e) => {
    const newEmail = e.target.value;
    setEmail(newEmail);
    setEmailTouched(true);
    
    // Reset existence state when email changes
    if (emailExists !== null) {
      setEmailExists(null);
    }
    
    // Clear existing timeout
    if (emailCheckTimeoutRef.current) {
      clearTimeout(emailCheckTimeoutRef.current);
    }
    
    // Only check if email looks valid
    if (newEmail.trim() && isValidEmail(newEmail.trim())) {
      // Debounce: wait 500ms after user stops typing
      emailCheckTimeoutRef.current = setTimeout(() => {
        checkEmailExists(newEmail.trim());
      }, 500);
    }
  };

  // Handle email blur - check immediately when user leaves field
  const handleEmailBlur = () => {
    setEmailTouched(true);
    
    // Clear any pending timeout
    if (emailCheckTimeoutRef.current) {
      clearTimeout(emailCheckTimeoutRef.current);
    }
    
    // Check email if it's valid and hasn't been checked yet
    if (email.trim() && isValidEmail(email.trim()) && emailExists === null) {
      checkEmailExists(email.trim());
    }
  };

  // Check if email exists in the system
  const checkEmailExists = async (emailToCheck) => {
    if (!emailToCheck || !isValidEmail(emailToCheck)) {
      setEmailExists(null);
      return;
    }

    setEmailChecking(true);
    try {
      const result = await checkEmailAvailability(emailToCheck);
      // If email is NOT available, it means it EXISTS (opposite of signup logic)
      setEmailExists(!result.available);
    } catch (error) {
      console.error('Error checking email:', error);
      // Fail silently - don't block login
      setEmailExists(null);
    } finally {
      setEmailChecking(false);
    }
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setErrorMsg('');
    setSuccessMsg('');

    try {
      const { data, error } = await supabase.auth.signInWithPassword({
        email: email.toLowerCase().trim(),
        password
      });

      if (error) {
        // Improved error messages
        const errorMessage = error.message.toLowerCase();
        
        if (errorMessage.includes('email not confirmed') || errorMessage.includes('email not verified')) {
          setErrorMsg('Please verify your email address before logging in. Check your inbox for a verification link.');
        } else if (errorMessage.includes('invalid login credentials') || 
                   errorMessage.includes('invalid credentials') ||
                   errorMessage.includes('invalid password') ||
                   errorMessage.includes('wrong password')) {
          // Check if email exists to provide better error message
          if (emailExists === false) {
            setErrorMsg('This email is not registered. Please sign up to create an account.');
          } else if (emailExists === true) {
            setErrorMsg('Invalid password. Please check your password or use "Forgot Password" to reset it.');
          } else {
            setErrorMsg('Invalid login credentials. Please check your email and password, or sign up if you don\'t have an account.');
          }
        } else {
          setErrorMsg(error.message);
        }
      } else {
        // Track successful sign in with user data
        trackEvents.signIn({
          email: email,
          user_id: data.user?.id,
          login_timestamp: new Date().toISOString()
        });
        
        // Smart redirect based on user's data
        performSmartRedirect(navigate);
      }
    } catch (err) {
      console.error(err);
      setErrorMsg('Something went wrong. Please try again later.');
    } finally {
      setLoading(false);
    }
  };

  const handlePasswordReset = async (e) => {
    e.preventDefault();
    setLoading(true);
    setErrorMsg('');
    setSuccessMsg('');

    if (!email.trim()) {
      setErrorMsg('Please enter your email address.');
      setLoading(false);
      return;
    }

    try {
      const { error } = await supabase.auth.resetPasswordForEmail(email.toLowerCase().trim(), {
        redirectTo: `${window.location.origin}/reset-password`,
      });

      if (error) {
        setErrorMsg(error.message);
      } else {
        setResetEmailSent(true);
        setSuccessMsg('Password reset email sent! Please check your inbox and follow the instructions to reset your password.');
        
        // Track password reset request
        trackEvents.passwordResetRequested?.({
          email: email,
          timestamp: new Date().toISOString()
        });
      }
    } catch (err) {
      console.error(err);
      setErrorMsg('Something went wrong. Please try again later.');
    } finally {
      setLoading(false);
    }
  };

  const handlePasswordVisibilityToggle = () => {
    setPasswordVisible((prev) => !prev);
  };

  return (
    <>
      <Navbar />
      <div className="min-h-screen flex items-center justify-center bg-[var(--color-bg)] px-4 py-8 sm:px-6 lg:px-8">
        <div className="w-full max-w-sm sm:max-w-md md:max-w-lg lg:max-w-md xl:max-w-md bg-[var(--color-card)] text-[var(--color-text-primary)] p-6 sm:p-8 rounded-2xl shadow-lg border border-[var(--color-border)]">
          <h2 className="text-2xl sm:text-3xl font-bold text-center mb-6 text-[var(--color-primary)]">
            {showForgotPassword ? 'Reset Password' : 'Welcome Back'}
          </h2>

          {errorMsg && (
            <div className="mb-4 p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800">
              <p className="text-[var(--color-error)] text-sm text-center">
                {errorMsg}
              </p>
              {errorMsg.includes('not registered') && (
                <p className="text-center mt-2">
                  <Link to="/signup" className="text-sm text-[var(--color-primary)] hover:underline">
                    Sign up now →
                  </Link>
                </p>
              )}
            </div>
          )}

          {successMsg && (
            <p className="text-green-600 dark:text-green-400 text-sm mb-4 text-center">
              {successMsg}
            </p>
          )}

          {resetEmailSent ? (
            <div className="text-center space-y-4">
              <FiMail className="w-16 h-16 text-[var(--color-primary)] mx-auto mb-4" />
              <p className="text-[var(--color-text-primary)]">
                We've sent a password reset link to <strong>{email}</strong>
              </p>
              <p className="text-sm text-[var(--color-text-secondary)]">
                Please check your email and click the link to reset your password. The link will expire in 1 hour.
              </p>
              <button
                onClick={() => {
                  setShowForgotPassword(false);
                  setResetEmailSent(false);
                  setEmail('');
                  setSuccessMsg('');
                }}
                className="text-[var(--color-primary)] hover:underline text-sm"
              >
                Back to Login
              </button>
            </div>
          ) : showForgotPassword ? (
            <form onSubmit={handlePasswordReset} className="space-y-5">
              <div>
                <label className="block text-sm font-medium mb-1 text-[var(--color-text-secondary)]">
                  Email
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  disabled={loading}
                  placeholder="Enter your email address"
                  className="w-full px-4 py-2 rounded-lg bg-[var(--color-input-bg)] border border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] transition"
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className={`w-full font-semibold py-2 rounded-lg transition ${
                  loading
                    ? 'bg-gray-400 cursor-not-allowed'
                    : 'bg-[var(--color-primary)] text-white hover:opacity-90 cursor-pointer'
                }`}
              >
                {loading ? 'Sending...' : 'Send Reset Link'}
              </button>

              <button
                type="button"
                onClick={() => {
                  setShowForgotPassword(false);
                  setErrorMsg('');
                  setSuccessMsg('');
                }}
                className="w-full text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-primary)]"
              >
                Back to Login
              </button>
            </form>
          ) : (
            <form onSubmit={handleLogin} className="space-y-5">
              {/* Email Input */}
              <div>
                <label className="block text-sm font-medium mb-1 text-[var(--color-text-secondary)]">
                  Email
                </label>
                <div className="relative">
                  <input
                    type="email"
                    value={email}
                    onChange={handleEmailChange}
                    onBlur={handleEmailBlur}
                    required
                    disabled={loading}
                    autoComplete="email"
                    className={`w-full px-4 py-2 pr-10 rounded-lg bg-[var(--color-input-bg)] text-[var(--color-text-primary)] border transition ${
                      emailTouched && email.trim()
                        ? emailExists === false
                          ? 'border-red-500 focus:ring-2 focus:ring-red-500'
                          : emailExists === true
                          ? 'border-green-500 focus:ring-2 focus:ring-green-500'
                          : 'border-[var(--color-border)] focus:ring-2 focus:ring-[var(--color-primary)]'
                        : 'border-[var(--color-border)] focus:ring-2 focus:ring-[var(--color-primary)]'
                    } focus:outline-none`}
                  />
                  {/* Email validation icon */}
                  <div className="absolute right-3 top-1/2 transform -translate-y-1/2">
                    {emailChecking ? (
                      <FiLoader className="w-5 h-5 text-blue-500 animate-spin" />
                    ) : emailTouched && email.trim() && isValidEmail(email.trim()) ? (
                      emailExists === true ? (
                        <FiCheckCircle className="w-5 h-5 text-green-500" />
                      ) : emailExists === false ? (
                        <FiAlertCircle className="w-5 h-5 text-red-500" />
                      ) : null
                    ) : null}
                  </div>
                </div>
                {/* Email existence message */}
                {emailTouched && email.trim() && isValidEmail(email.trim()) && !emailChecking && emailExists === false && (
                  <div className="mt-1 text-xs">
                    <p className="text-red-600 dark:text-red-400 flex items-center gap-1">
                      <FiAlertCircle className="w-3 h-3" />
                      This email is not registered. <Link to="/signup" className="underline font-medium">Sign up instead?</Link>
                    </p>
                  </div>
                )}
              </div>

              {/* Password Input */}
              <div>
                <label className="block text-sm font-medium mb-1 text-[var(--color-text-secondary)]">
                  Password
                </label>
                <div className="relative">
                  <input
                    type={passwordVisible ? 'text' : 'password'}
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    disabled={loading}
                    className="w-full px-4 py-2 rounded-lg bg-[var(--color-input-bg)] text-[var(--color-text-primary)] border border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] transition"
                  />
                  <button
                    type="button"
                    onClick={handlePasswordVisibilityToggle}
                    className="absolute right-3 top-1/2 transform -translate-y-1/2 text-[var(--color-text-secondary)] hover:text-[var(--color-primary)] cursor-pointer"
                    aria-label="Toggle password visibility"
                  >
                    {passwordVisible ? (
                      <FiEyeOff className="w-5 h-5" />
                    ) : (
                      <FiEye className="w-5 h-5" />
                    )}
                  </button>
                </div>
              </div>

              {/* Forgot Password Link */}
              <div className="text-right">
                <button
                  type="button"
                  onClick={() => setShowForgotPassword(true)}
                  className="text-sm text-[var(--color-primary)] hover:underline"
                >
                  Forgot Password?
                </button>
              </div>

              {/* Submit Button */}
              <button
                type="submit"
                disabled={loading}
                className={`w-full font-semibold py-2 rounded-lg transition ${
                  loading
                    ? 'bg-gray-400 cursor-not-allowed'
                    : 'bg-[var(--color-primary)] text-white hover:opacity-90 cursor-pointer'
                }`}
              >
                {loading ? 'Logging in...' : 'Login'}
              </button>
            </form>
          )}

          {/* Signup Link */}
          {!showForgotPassword && (
            <p className="mt-6 text-center text-sm text-[var(--color-text-secondary)]">
              Don't have an account?{' '}
              <Link to="/signup" className="text-[var(--color-primary)] hover:underline">
                Sign up
              </Link>
            </p>
          )}
        </div>
      </div>
    </>
  );
}

export default Login;