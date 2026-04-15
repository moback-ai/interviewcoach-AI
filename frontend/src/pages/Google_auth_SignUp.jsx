import React, { useState } from 'react';
import { supabase } from '../supabaseClient';
import { useNavigate, Link } from 'react-router-dom';
import { useTheme } from '../hooks/useTheme';
import { FiEye, FiEyeOff } from 'react-icons/fi';

function Signup() {
  const navigate = useNavigate();
  const { theme } = useTheme();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errorMsg, setErrorMsg] = useState('');
  const [successMsg, setSuccessMsg] = useState('');
  const [loading, setLoading] = useState(false);
  const [passwordVisible, setPasswordVisible] = useState(false); // Track visibility


const handleSignup = async (e) => {
  e.preventDefault();
  setLoading(true);
  setErrorMsg('');
  setSuccessMsg('');

  if (password.length < 8) {
    setErrorMsg('Password must be at least 8 characters long.');
    setLoading(false);
    return;
  }

  try {
    const { data, error } = await supabase.auth.signUp({ email, password });

    if (error) {
      // Show the raw message for debugging, optionally customize below
      if (error.status === 400 && error.message.includes('already registered')) {
        setErrorMsg('This email is already in use. Try logging in instead.');
      } else {
        setErrorMsg(error.message);
      }
    } else {
      // Handle both first-time and re-sent confirmations
      setSuccessMsg('Check your email to confirm your account.');
      setTimeout(() => navigate('/'), 3000);
    }
  } catch (err) {
    console.error(err);
    setErrorMsg('Something went wrong. Please try again later.');
  } finally {
    setLoading(false);
  }
};


const handlePasswordVisibilityToggle = () => {
  setPasswordVisible(!passwordVisible);
};


  const handleOAuthLogin = async () => {
    setLoading(true);
    setErrorMsg('');
    try {
      const { error } = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: {
          redirectTo: window.location.origin + '/oauth/callback'
        }
      });

      if (error) {
        setErrorMsg('Google sign-in failed. Please try again.');
      }
    } catch (err) {
      setErrorMsg('An unexpected error occurred during Google login.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--color-bg)] px-4">
      <form
        onSubmit={handleSignup}
        className="w-full max-w-md bg-[var(--color-card)] text-[var(--color-text-primary)] p-8 rounded-2xl shadow-lg border border-[var(--color-border)]"
        aria-label="Signup Form"
      >
        <h2 className="text-3xl font-bold text-center mb-6 text-[var(--color-primary)] dark:text-white">
          Create an Account
        </h2>

        {errorMsg && <p className="text-red-500 mb-4 text-sm text-center">{errorMsg}</p>}
        {successMsg && <p className="text-green-500 mb-4 text-sm text-center">{successMsg}</p>}

        <div className="mb-4">
          <label htmlFor="email" className="block text-sm font-medium mb-1 text-[var(--color-text-secondary)]">
            Email
          </label>
          <input
            id="email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            disabled={loading}
            className="w-full px-4 py-2 rounded-lg bg-[var(--color-input-bg)] text-[var(--color-text-primary)] border border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] transition"
          />
        </div>

<div className="mb-6">
  <label htmlFor="password" className="block text-sm font-medium mb-1 text-[var(--color-text-secondary)]">
    Password
  </label>
  <div className="relative">
    <input
      id="password"
      type={passwordVisible ? 'text' : 'password'} // Toggle between password and text
      autoComplete="new-password"
      value={password}
      onChange={(e) => setPassword(e.target.value)}
      required
      disabled={loading}
      className="w-full px-4 py-2 rounded-lg bg-[var(--color-input-bg)] text-[var(--color-text-primary)] border border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] transition"
    />
    <button
      type="button"
      onClick={handlePasswordVisibilityToggle}
      className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-500 hover:text-gray-700"
    >
      {passwordVisible ? (
        <FiEyeOff className="w-5 h-5" />
      ) : (
        <FiEye className="w-5 h-5" />
      )}
    </button>
  </div>
</div>


        <button
          type="submit"
          disabled={loading}
          className={`w-full py-2 font-semibold rounded transition text-white ${
            loading ? 'bg-gray-400 cursor-not-allowed' : 'bg-[var(--color-primary)] hover:opacity-90'
          }`}
        >
          {loading ? 'Creating account...' : 'Sign Up'}
        </button>

        {/* <div className="relative my-6">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-gray-300 dark:border-gray-600" />
          </div>
          <div className="relative flex justify-center text-sm">
            <span className="bg-[var(--color-card)] px-2 text-[var(--color-text-secondary)]">OR</span>
          </div>
        </div> */}

        {/* <button
          type="button"
          onClick={handleOAuthLogin}
          disabled={loading}
          className="w-full py-2 font-semibold rounded flex items-center justify-center gap-2 bg-white text-gray-700 border border-gray-300 hover:bg-gray-100 transition dark:bg-gray-800 dark:text-white dark:border-gray-600"
        >
          <img
            src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/google/google-original.svg"
            alt="Google"
            className="h-5 w-5"
          />
          Continue with Google
        </button> */}

        <p className="mt-6 text-sm text-center text-[var(--color-text-secondary)]">
          Already have an account?{' '}
          <Link to="/login" className="text-[var(--color-primary)] hover:underline">
            Login
          </Link>
        </p>
      </form>
    </div>
  );
}

export default Signup;