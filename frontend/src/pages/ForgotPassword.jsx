import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { FiArrowLeft, FiKey, FiMail } from 'react-icons/fi';
import Navbar from '../components/Navbar';
import AuthSceneShell from '../components/auth/AuthSceneShell';
import { useTheme } from '../hooks/useTheme';
import { forgotPassword, isValidEmail } from '../lib/authClient';
import { buildLoginCoachState } from '../utils/authCoachNotice';

function ForgotPassword() {
  const navigate = useNavigate();
  useTheme();
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setErrorMsg('');

    try {
      const normalizedEmail = email.toLowerCase().trim();
      const data = await forgotPassword(email);
      navigate('/login', {
        replace: true,
        state: buildLoginCoachState({
          identifier: normalizedEmail,
          notice: {
            tone: 'success',
            title: 'Reset link sent',
            message: data.message || `If an account exists for ${normalizedEmail}, a password reset link has been sent.`,
            actionLabel: data.reset_link ? 'Open reset link' : '',
            actionHref: data.reset_link || '',
          },
        }),
      });
    } catch (error) {
      setErrorMsg(error.message || 'Unable to send password reset link.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Navbar />
      <AuthSceneShell
        variant="night"
        badge="Reset access"
        icon={<FiKey size={18} />}
        title="Forgot your password?"
        description="Enter the email tied to your account and we’ll send a secure reset link so you can get back into your interview workspace."
        footer={(
          <p className="text-sm text-center text-[var(--color-text-secondary)]">
            Remembered it?{' '}
            <Link to="/login" className="auth-scene-link-inline">
              Back to login
            </Link>
          </p>
        )}
      >
        {errorMsg && (
          <div className="auth-scene-alert auth-scene-alert-error">
            {errorMsg}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="auth-scene-label">Email</label>
            <div className="auth-scene-input-wrap">
              <span className="auth-scene-input-icon">
                <FiMail size={16} />
              </span>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                disabled={loading}
                className="auth-scene-input"
                placeholder="you@example.com"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading || !isValidEmail(email.trim())}
            className="auth-scene-submit"
          >
            {loading ? 'Sending...' : 'Send reset link'}
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

export default ForgotPassword;
