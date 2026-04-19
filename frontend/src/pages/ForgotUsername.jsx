import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import Navbar from '../components/Navbar';
import { useTheme } from '../hooks/useTheme';
import { forgotUsername, isValidEmail } from '../lib/authClient';

function ForgotUsername() {
  useTheme();
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [infoMsg, setInfoMsg] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setErrorMsg('');
    setInfoMsg('');

    try {
      const data = await forgotUsername(email);
      const manualHint =
        data.delivery === 'manual' && data.username
          ? ` Username: ${data.username}`
          : '';
      setInfoMsg((data.message || 'If an account exists, the username reminder has been sent.') + manualHint);
    } catch (error) {
      setErrorMsg(error.message || 'Unable to recover username right now.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Navbar />
      <div className="min-h-screen flex items-center justify-center bg-[var(--color-bg)] px-4 py-8">
        <div className="w-full max-w-md bg-[var(--color-card)] text-[var(--color-text-primary)] p-8 rounded-2xl shadow-lg border border-[var(--color-border)]">
          <h2 className="text-3xl font-bold text-center mb-3 text-[var(--color-primary)]">Forgot Username</h2>
          <p className="text-sm text-center text-[var(--color-text-secondary)] mb-6">
            Enter your signup email and we&apos;ll help you recover your username.
          </p>

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

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-sm font-medium mb-1 text-[var(--color-text-secondary)]">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                disabled={loading}
                className="w-full px-4 py-2 rounded-lg bg-[var(--color-input-bg)] border border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] transition"
                placeholder="you@example.com"
              />
            </div>

            <button
              type="submit"
              disabled={loading || !isValidEmail(email.trim())}
              className="w-full py-2.5 rounded-lg bg-[var(--color-primary)] text-white font-medium hover:opacity-90 transition disabled:opacity-50"
            >
              {loading ? 'Recovering...' : 'Recover username'}
            </button>
          </form>

          <p className="text-sm text-center mt-6 text-[var(--color-text-secondary)]">
            Back to{' '}
            <Link to="/login" className="text-[var(--color-primary)] hover:underline">
              login
            </Link>
          </p>
        </div>
      </div>
    </>
  );
}

export default ForgotUsername;
