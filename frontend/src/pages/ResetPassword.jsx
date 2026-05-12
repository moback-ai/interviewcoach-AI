import React, { useMemo, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { FiArrowLeft, FiCheckCircle, FiLock } from 'react-icons/fi';
import Navbar from '../components/Navbar';
import AuthSceneShell from '../components/auth/AuthSceneShell';
import { useTheme } from '../hooks/useTheme';
import { resetPassword } from '../lib/authClient';
import { buildLoginCoachState } from '../utils/authCoachNotice';

function ResetPassword() {
  useTheme();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const token = useMemo(() => params.get('token') || '', [params]);
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  const passwordIsValid = password.length >= 8;
  const passwordsMatch = password && password === confirmPassword;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setErrorMsg('');

    try {
      const data = await resetPassword(token, password);
      navigate('/login', {
        replace: true,
        state: buildLoginCoachState({
          notice: {
            tone: 'success',
            title: 'Password updated',
            message: data.message || 'Your password reset is complete. Sign in now with your new password.',
          },
        }),
      });
    } catch (error) {
      setErrorMsg(error.message || 'Unable to reset password.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Navbar />
      <AuthSceneShell
        variant="emerald"
        badge="Secure reset"
        icon={<FiLock size={18} />}
        title="Create a fresh password"
        description="Choose a password you’ll remember but others can’t guess. Once it’s updated, we’ll send you straight back to sign in."
        footer={(
          <p className="text-sm text-center text-[var(--color-text-secondary)]">
            Back to{' '}
            <Link to="/login" className="auth-scene-link-inline">
              login
            </Link>
          </p>
        )}
      >
        {!token && (
          <div className="auth-scene-alert auth-scene-alert-error">
            Reset token is missing or invalid.
          </div>
        )}

        {errorMsg && (
          <div className="auth-scene-alert auth-scene-alert-error">
            {errorMsg}
          </div>
        )}

        {!errorMsg && token && password.length > 0 && (
          <div className="auth-scene-alert auth-scene-alert-soft">
            <FiCheckCircle size={15} />
            <span>{passwordsMatch ? 'Passwords match and are ready to submit.' : 'Use at least 8 characters and make both entries match.'}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="auth-scene-label">New password</label>
            <div className="auth-scene-input-wrap">
              <span className="auth-scene-input-icon">
                <FiLock size={16} />
              </span>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                disabled={loading || !token}
                className="auth-scene-input"
                placeholder="At least 8 characters"
              />
            </div>
          </div>

          <div>
            <label className="auth-scene-label">Confirm password</label>
            <div className="auth-scene-input-wrap">
              <span className="auth-scene-input-icon">
                <FiCheckCircle size={16} />
              </span>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                disabled={loading || !token}
                className="auth-scene-input"
                placeholder="Re-enter your new password"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading || !token || !passwordIsValid || !passwordsMatch}
            className="auth-scene-submit"
          >
            {loading ? 'Resetting...' : 'Reset password'}
          </button>
        </form>

        <Link to="/login" className="auth-scene-link-row">
          <FiArrowLeft size={15} />
          <span>Return to sign in</span>
        </Link>
      </AuthSceneShell>
    </>
  );
}

export default ResetPassword;
