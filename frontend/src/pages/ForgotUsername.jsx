import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { FiArrowLeft, FiMail, FiUser } from 'react-icons/fi';
import Navbar from '../components/Navbar';
import AuthSceneShell from '../components/auth/AuthSceneShell';
import { useTheme } from '../hooks/useTheme';
import { forgotUsername, isValidEmail } from '../lib/authClient';
import { buildLoginCoachState } from '../utils/authCoachNotice';

function ForgotUsername() {
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
      const data = await forgotUsername(email);
      const manualHint =
        data.delivery === 'manual' && data.username
          ? ` Username: ${data.username}`
          : '';
      navigate('/login', {
        replace: true,
        state: buildLoginCoachState({
          identifier: normalizedEmail,
          notice: {
            tone: 'success',
            title: 'Username reminder sent',
            message: (data.message || 'If an account exists, the username reminder has been sent.') + manualHint,
          },
        }),
      });
    } catch (error) {
      setErrorMsg(error.message || 'Unable to recover username right now.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Navbar />
      <AuthSceneShell
        variant="marine"
        badge="Recover username"
        icon={<FiUser size={18} />}
        title="Need your username again?"
        description="Use the email you signed up with and we’ll send a reminder so you can step back into the platform without guessing."
        footer={(
          <p className="text-sm text-center text-[var(--color-text-secondary)]">
            Back to{' '}
            <Link to="/login" className="auth-scene-link-inline">
              login
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
            {loading ? 'Recovering...' : 'Recover username'}
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

export default ForgotUsername;
