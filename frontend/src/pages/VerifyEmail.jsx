import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import Navbar from '../components/Navbar';
import { useTheme } from '../hooks/useTheme';
import { useAuth } from '../contexts/AuthContext';

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
      .then(() => {
        if (!mounted) return;
        setStatus('success');
        setMessage('Email verified successfully. Redirecting to your dashboard...');
        window.setTimeout(() => navigate('/dashboard'), 1200);
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

  return (
    <>
      <Navbar />
      <div className="min-h-screen flex items-center justify-center bg-[var(--color-bg)] px-4 py-8">
        <div className="w-full max-w-md bg-[var(--color-card)] text-[var(--color-text-primary)] p-8 rounded-2xl shadow-lg border border-[var(--color-border)] text-center">
          <h2 className="text-3xl font-bold mb-4 text-[var(--color-primary)]">Verify Email</h2>
          <p className={status === 'error' ? 'text-red-600' : 'text-[var(--color-text-secondary)]'}>
            {message}
          </p>
          {status === 'error' && (
            <Link to="/login" className="inline-block mt-6 text-[var(--color-primary)] hover:underline">
              Go back to login
            </Link>
          )}
        </div>
      </div>
    </>
  );
}

export default VerifyEmail;
