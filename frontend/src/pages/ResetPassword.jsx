import React, { useState, useEffect, useRef } from 'react';
import { supabase } from '../supabaseClient';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useTheme } from '../hooks/useTheme';
import { FiEye, FiEyeOff, FiCheckCircle } from 'react-icons/fi';
import Navbar from '../components/Navbar';

function ResetPassword() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { theme } = useTheme();
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [passwordVisible, setPasswordVisible] = useState(false);
  const [confirmPasswordVisible, setConfirmPasswordVisible] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [successMsg, setSuccessMsg] = useState('');
  const [loading, setLoading] = useState(false);
  const [passwordReset, setPasswordReset] = useState(false);
  const [tokensReady, setTokensReady] = useState(false);
  const [storedTokens, setStoredTokens] = useState(null);
  const tokensProcessedRef = useRef(false); // Track if we've already processed tokens

  useEffect(() => {
    let mounted = true;
    let authSubscription = null;

    // If we've already processed tokens, don't run again
    if (tokensProcessedRef.current) {
      return () => {
        mounted = false;
        if (authSubscription) {
          authSubscription.unsubscribe();
        }
      };
    }

    // Function to extract tokens from hash or search params
    const extractTokens = () => {
      // Check hash first (most common)
      const hash = window.location.hash;
      if (hash) {
        try {
          const hashParams = new URLSearchParams(hash.substring(1));
          const type = hashParams.get('type');
          const accessToken = hashParams.get('access_token');
          const refreshToken = hashParams.get('refresh_token');
          
          if (type === 'recovery' && accessToken && refreshToken) {
            return { accessToken, refreshToken, type };
          }
        } catch (error) {
          console.error('Error parsing hash:', error);
        }
      }

      // Check search params (sometimes Supabase puts tokens here)
      const type = searchParams.get('type');
      const accessToken = searchParams.get('access_token');
      const refreshToken = searchParams.get('refresh_token');
      
      if (type === 'recovery' && accessToken && refreshToken) {
        return { accessToken, refreshToken, type };
      }

      return null;
    };

    // Listen for auth state changes (Supabase processes recovery links automatically)
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      async (event, session) => {
        if (!mounted || tokensProcessedRef.current) return;

        console.log('Auth state change:', event, session?.user?.email);
        
        // Handle password recovery - Supabase automatically processes recovery links
        if (event === 'PASSWORD_RECOVERY' || 
            (event === 'SIGNED_IN' && session?.user && window.location.hash.includes('type=recovery'))) {
          console.log('Password recovery detected via auth state change');
          tokensProcessedRef.current = true;
          setTokensReady(true);
          // Clean up URL
          window.history.replaceState({}, document.title, '/reset-password');
          return;
        }

        // If we get a session and we're on reset-password page, allow reset
        if (event === 'SIGNED_IN' && session?.user && location.pathname === '/reset-password') {
          // Check if this might be from a recovery link (session was just created)
          const sessionAge = Date.now() - new Date(session.user.created_at).getTime();
          // If session is very new (less than 5 minutes), it might be from recovery
          if (sessionAge < 300000 || window.location.hash.includes('recovery')) {
            console.log('New session detected, allowing password reset');
            tokensProcessedRef.current = true;
            setTokensReady(true);
            window.history.replaceState({}, document.title, '/reset-password');
          }
        }
      }
    );

    authSubscription = subscription;

    // Try to extract tokens immediately (before Supabase processes them)
    const tokens = extractTokens();
    
    if (tokens) {
      console.log('Tokens found in URL');
      // Mark as processed to prevent re-running
      tokensProcessedRef.current = true;
      
      // Store tokens but DON'T set session yet
      setStoredTokens({ accessToken: tokens.accessToken, refreshToken: tokens.refreshToken });
      setTokensReady(true);
      
      // Clean up URL immediately to prevent Supabase from auto-processing
      window.history.replaceState({}, document.title, '/reset-password');
      
      // Return early - don't check for session when we have tokens
      return () => {
        mounted = false;
        if (authSubscription) {
          authSubscription.unsubscribe();
        }
      };
    } else {
      // No tokens in URL - check if Supabase already processed it and created a session
      // But only if we haven't already processed tokens
      if (tokensProcessedRef.current) {
        return () => {
          mounted = false;
          if (authSubscription) {
            authSubscription.unsubscribe();
          }
        };
      }

      const checkSession = async () => {
        try {
          const { data: { session }, error } = await supabase.auth.getSession();
          
          if (!mounted || tokensProcessedRef.current) return;

          if (session && session.user) {
            console.log('Session found, allowing password reset');
            tokensProcessedRef.current = true;
            // User has a session - might be from recovery link
            setTokensReady(true);
          } else {
            // Wait a bit longer - Supabase might still be processing
            console.log('No session yet, waiting...');
            
            // Check multiple times with increasing delays
            const delays = [500, 1000, 2000];
            for (const delay of delays) {
              await new Promise(resolve => setTimeout(resolve, delay));
              
              if (!mounted || tokensProcessedRef.current) return;
              
              const { data: { delayedSession } } = await supabase.auth.getSession();
              if (delayedSession && delayedSession.user) {
                console.log('Session found after delay, allowing password reset');
                tokensProcessedRef.current = true;
                setTokensReady(true);
                return;
              }
            }

            // Final check - look for any recovery indicators in the original URL
            // Check if hash was recently cleared (might have been a recovery link)
            const currentHash = window.location.hash;
            const hasRecoveryInHash = currentHash.includes('recovery') || currentHash.includes('type=recovery');
            
            // Also check if we came from a redirect (document.referrer might help)
            const cameFromEmail = document.referrer.includes('mail') || 
                                  document.referrer.includes('email') ||
                                  window.location.search.includes('recovery');
            
            if (!hasRecoveryInHash && !session && !cameFromEmail) {
              console.log('No reset link found after all checks');
              if (!tokensProcessedRef.current) {
                setErrorMsg('No reset link found. Please request a new password reset from the login page.');
              }
            } else if (cameFromEmail || hasRecoveryInHash) {
              // Might be a recovery link that was processed - allow reset
              console.log('Recovery link detected, allowing password reset');
              tokensProcessedRef.current = true;
              setTokensReady(true);
            }
          }
        } catch (error) {
          console.error('Error checking session:', error);
          if (mounted && !tokensProcessedRef.current) {
            setErrorMsg('Error verifying reset link. Please try requesting a new password reset.');
          }
        }
      };

      checkSession();
    }

    return () => {
      mounted = false;
      if (authSubscription) {
        authSubscription.unsubscribe();
      }
    };
  }, [searchParams, location.pathname]);

  const handlePasswordReset = async (e) => {
    e.preventDefault();
    setLoading(true);
    setErrorMsg('');
    setSuccessMsg('');

    // Validation
    if (password.length < 8) {
      setErrorMsg('Password must be at least 8 characters long.');
      setLoading(false);
      return;
    }

    if (password !== confirmPassword) {
      setErrorMsg('Passwords do not match.');
      setLoading(false);
      return;
    }

    try {
      // If we have stored tokens, set the session now (just before resetting)
      if (storedTokens) {
        const { error: sessionError } = await supabase.auth.setSession({
          access_token: storedTokens.accessToken,
          refresh_token: storedTokens.refreshToken,
        });

        if (sessionError) {
          setErrorMsg('Reset link has expired. Please request a new password reset.');
          setLoading(false);
          return;
        }
      }

      // Verify we have a session
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) {
        setErrorMsg('Session expired. Please request a new password reset link.');
        setLoading(false);
        return;
      }

      // Update password
      const { error } = await supabase.auth.updateUser({
        password: password
      });

      if (error) {
        setErrorMsg(error.message);
      } else {
        // Sign out the user after password reset (security best practice)
        await supabase.auth.signOut();
        
        setPasswordReset(true);
        setSuccessMsg('Password reset successfully! Redirecting to login...');
        
        setTimeout(() => {
          navigate('/login');
        }, 2000);
      }
    } catch (err) {
      console.error(err);
      setErrorMsg('Something went wrong. Please try again later.');
    } finally {
      setLoading(false);
    }
  };

  if (passwordReset) {
    return (
      <>
        <Navbar />
        <div className="min-h-screen flex items-center justify-center bg-[var(--color-bg)] px-4">
          <div className="w-full max-w-md bg-[var(--color-card)] text-[var(--color-text-primary)] p-8 rounded-2xl shadow-lg border border-[var(--color-border)] text-center">
            <FiCheckCircle className="w-16 h-16 text-green-500 mx-auto mb-4" />
            <h2 className="text-2xl font-bold mb-4 text-[var(--color-primary)]">
              Password Reset Successful!
            </h2>
            <p className="text-[var(--color-text-secondary)] mb-4">
              Your password has been reset successfully. You can now log in with your new password.
            </p>
            <p className="text-sm text-[var(--color-text-secondary)]">
              Redirecting to login page...
            </p>
          </div>
        </div>
      </>
    );
  }

  if (!tokensReady && !errorMsg) {
    return (
      <>
        <Navbar />
        <div className="min-h-screen flex items-center justify-center bg-[var(--color-bg)] px-4">
          <div className="w-full max-w-md bg-[var(--color-card)] text-[var(--color-text-primary)] p-8 rounded-2xl shadow-lg border border-[var(--color-border)] text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[var(--color-primary)] mx-auto mb-4"></div>
            <p className="text-[var(--color-text-secondary)]">
              Verifying reset link...
            </p>
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <Navbar />
      <div className="min-h-screen flex items-center justify-center bg-[var(--color-bg)] px-4 py-8 sm:px-6 lg:px-8">
        <div className="w-full max-w-sm sm:max-w-md bg-[var(--color-card)] text-[var(--color-text-primary)] p-6 sm:p-8 rounded-2xl shadow-lg border border-[var(--color-border)]">
          <h2 className="text-2xl sm:text-3xl font-bold text-center mb-6 text-[var(--color-primary)]">
            Reset Password
          </h2>

          {errorMsg && (
            <div className="mb-4">
              <p className="text-[var(--color-error)] text-sm text-center mb-2">
                {errorMsg}
              </p>
              {errorMsg.includes('expired') || errorMsg.includes('Invalid') || errorMsg.includes('No reset link') ? (
                <a
                  href="/login"
                  className="text-sm text-[var(--color-primary)] hover:underline block text-center"
                >
                  Request a new reset link
                </a>
              ) : null}
            </div>
          )}

          {successMsg && (
            <p className="text-green-600 dark:text-green-400 text-sm mb-4 text-center">
              {successMsg}
            </p>
          )}

          {tokensReady && (
            <form onSubmit={handlePasswordReset} className="space-y-5">
              {/* New Password */}
              <div>
                <label className="block text-sm font-medium mb-1 text-[var(--color-text-secondary)]">
                  New Password
                </label>
                <div className="relative">
                  <input
                    type={passwordVisible ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    disabled={loading}
                    minLength={8}
                    className="w-full px-4 py-2 rounded-lg bg-[var(--color-input-bg)] text-[var(--color-text-primary)] border border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] transition"
                  />
                  <button
                    type="button"
                    onClick={() => setPasswordVisible(!passwordVisible)}
                    className="absolute right-3 top-1/2 transform -translate-y-1/2 text-[var(--color-text-secondary)] hover:text-[var(--color-primary)] cursor-pointer"
                  >
                    {passwordVisible ? (
                      <FiEyeOff className="w-5 h-5" />
                    ) : (
                      <FiEye className="w-5 h-5" />
                    )}
                  </button>
                </div>
                <p className="text-xs text-[var(--color-text-secondary)] mt-1">
                  Must be at least 8 characters long
                </p>
              </div>

              {/* Confirm Password */}
              <div>
                <label className="block text-sm font-medium mb-1 text-[var(--color-text-secondary)]">
                  Confirm Password
                </label>
                <div className="relative">
                  <input
                    type={confirmPasswordVisible ? 'text' : 'password'}
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    required
                    disabled={loading}
                    minLength={8}
                    className="w-full px-4 py-2 rounded-lg bg-[var(--color-input-bg)] text-[var(--color-text-primary)] border border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] transition"
                  />
                  <button
                    type="button"
                    onClick={() => setConfirmPasswordVisible(!confirmPasswordVisible)}
                    className="absolute right-3 top-1/2 transform -translate-y-1/2 text-[var(--color-text-secondary)] hover:text-[var(--color-primary)] cursor-pointer"
                  >
                    {confirmPasswordVisible ? (
                      <FiEyeOff className="w-5 h-5" />
                    ) : (
                      <FiEye className="w-5 h-5" />
                    )}
                  </button>
                </div>
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
                {loading ? 'Resetting...' : 'Reset Password'}
              </button>
            </form>
          )}

          <p className="mt-6 text-center text-sm text-[var(--color-text-secondary)]">
            Remember your password?{' '}
            <a
              href="/login"
              className="text-[var(--color-primary)] hover:underline"
            >
              Login
            </a>
          </p>
        </div>
      </div>
    </>
  );
}

export default ResetPassword;
