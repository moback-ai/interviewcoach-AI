import React, { useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import Navbar from '../components/Navbar';
import { useTheme } from '../hooks/useTheme';
import { resetPassword } from '../lib/authClient';

function ResetPassword() {
  useTheme();
  const [params] = useSearchParams();
  const token = useMemo(() => params.get('token') || '', [params]);
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [infoMsg, setInfoMsg] = useState('');

  const passwordIsValid = password.length >= 8;
  const passwordsMatch = password && password === confirmPassword;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setErrorMsg('');
    setInfoMsg('');

    try {
      const data = await resetPassword(token, password);
      setInfoMsg(data.message || 'Password reset successful. You can log in now.');
      setPassword('');
      setConfirmPassword('');
    } catch (error) {
      setErrorMsg(error.message || 'Unable to reset password.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Navbar />
      <div className="min-h-screen flex items-center justify-center bg-[var(--color-bg)] px-4 py-8">
        <div className="w-full max-w-md bg-[var(--color-card)] text-[var(--color-text-primary)] p-8 rounded-2xl shadow-lg border border-[var(--color-border)]">
          <h2 className="text-3xl font-bold text-center mb-3 text-[var(--color-primary)]">Reset Password</h2>
          <p className="text-sm text-center text-[var(--color-text-secondary)] mb-6">
            Choose a new password for your account.
          </p>

          {!token && (
            <div className="mb-4 p-3 rounded-lg bg-red-50 border border-red-200 text-red-600 text-sm text-center">
              Reset token is missing or invalid.
            </div>
          )}

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
              <label className="block text-sm font-medium mb-1 text-[var(--color-text-secondary)]">New password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                disabled={loading || !token}
                className="w-full px-4 py-2 rounded-lg bg-[var(--color-input-bg)] border border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] transition"
                placeholder="At least 8 characters"
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-1 text-[var(--color-text-secondary)]">Confirm password</label>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                disabled={loading || !token}
                className="w-full px-4 py-2 rounded-lg bg-[var(--color-input-bg)] border border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] transition"
                placeholder="Re-enter your new password"
              />
            </div>

            <button
              type="submit"
              disabled={loading || !token || !passwordIsValid || !passwordsMatch}
              className="w-full py-2.5 rounded-lg bg-[var(--color-primary)] text-white font-medium hover:opacity-90 transition disabled:opacity-50"
            >
              {loading ? 'Resetting...' : 'Reset password'}
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

export default ResetPassword;
