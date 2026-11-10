import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { FiAlertCircle, FiCheckCircle, FiLoader, FiMail } from 'react-icons/fi';
import Navbar from '../components/Navbar';
import AuthSceneShell from '../components/auth/AuthSceneShell';
import { useTheme } from '../hooks/useTheme';
import { useAuth } from '../contexts/AuthContext';
import { createAuthCoachNotice } from '../utils/authCoachNotice';

function VerifyEmail() {
  useTheme();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { confirmEmail } = useAuth();
  const [status, setStatus] = useState('loading');
  const [message, setMessage] = useState('Verifying your email...');

  const token = useMemo(() => searchParams.get('token') || '', [searchParams]);

  useEffect(() => {
    if (!token) {
      setStatus('error');
      setMessage('This verification link is missing its token.');
      return;
    }

    let mounted = true;
    confirmEmail(token)
      .then((data) => {
        if (!mounted) return;
        setStatus('success');
        setMessage('Email verified successfully. Redirecting to login...');
        window.setTimeout(() => navigate('/login', {
          replace: true,
          state: {
            prefillIdentifier: data?.email || '',
            authNotice: createAuthCoachNotice({
              tone: 'success',
              title: 'Email verified',
              message: 'Your email is confirmed. Enter your password to sign in.',
            }),
          },
        }), 1200);
      })
      .catch((error) => {
        if (!mounted) return;
        setStatus('error');
        setMessage(error.message || 'This verification link is invalid or expired.');
      });

    return () => {
      mounted = false;
    };
  }, [confirmEmail, navigate, token]);

  const badge = status === 'success' ? 'Verified' : status === 'error' ? 'Action needed' : 'Verifying';
  const title = status === 'success'
    ? 'Your email is confirmed'
    : status === 'error'
      ? 'This verification link needs attention'
      : 'Checking your verification link';
  const icon = status === 'success'
    ? <FiCheckCircle size={18} />
    : status === 'error'
      ? <FiAlertCircle size={18} />
      : <FiLoader size={18} className="auth-scene-spinner" />;

  return (
    <>
      <Navbar />
      <AuthSceneShell
        variant={status === 'success' ? 'emerald' : 'night'}
        badge={badge}
        icon={icon}
        title={title}
        description="We’re validating your email so you can sign in to your interview dashboard."
      >
        <div className={`auth-scene-alert ${status === 'error' ? 'auth-scene-alert-error' : 'auth-scene-alert-soft'}`} role={status === 'error' ? 'alert' : undefined}>
          {status !== 'success' ? <FiMail size={15} /> : <FiCheckCircle size={15} />}
          <span>{message}</span>
        </div>

        {status === 'error' && (
          <div className="pt-2 text-center">
            <Link to="/login" className="auth-scene-link-inline">
              Go back to login
            </Link>
          </div>
        )}
      </AuthSceneShell>
    </>
  );
}

export default VerifyEmail;
