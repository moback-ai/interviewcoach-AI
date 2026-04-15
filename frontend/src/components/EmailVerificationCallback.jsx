import React, { useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useTheme } from '../hooks/useTheme';
import { useEmailVerification } from '../hooks/useEmailVerification';
import { FiCheckCircle, FiXCircle, FiLoader, FiUpload, FiArrowRight } from 'react-icons/fi';
import Navbar from './Navbar';
import { performSmartRedirect } from '../utils/smartRouting';
import { trackEvents } from '../services/mixpanel';

function EmailVerificationCallback() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { theme } = useTheme();
  const { verificationStatus, verificationMessage, handleEmailVerification } = useEmailVerification();
  const hasTrackedEvent = useRef(false); // Prevent duplicate tracking

  useEffect(() => {
    const processVerification = async () => {
      // Check if this is a password reset (recovery) link
      const type = searchParams.get('type');
      const accessToken = searchParams.get('access_token');
      const hash = window.location.hash;
      
      // If it's a password reset, redirect to reset password page with the hash
      if (type === 'recovery' || (hash && hash.includes('type=recovery'))) {
        // Preserve the hash/tokens and redirect to reset password page
        const hashParams = new URLSearchParams(hash.substring(1)); // Remove #
        const redirectUrl = `/reset-password${hash ? `#${hash.substring(1)}` : ''}${accessToken ? `?access_token=${accessToken}` : ''}`;
        navigate(redirectUrl, { replace: true });
        return;
      }

      // Otherwise, handle as email verification
      const result = await handleEmailVerification(searchParams);
      if (result.success && !hasTrackedEvent.current) {
        // Track email verification success (only once)
        hasTrackedEvent.current = true;
        trackEvents.emailVerified({
          email: result.email,
          user_id: result.user_id,
          verification_timestamp: new Date().toISOString()
        });
        
        // Smart redirect based on user's data
        setTimeout(() => performSmartRedirect(navigate), 2000);
      }
    };

    processVerification();
  }, [searchParams, navigate, handleEmailVerification]); // ✅ Now safe to include since it's memoized

  const getStatusIcon = () => {
    switch (verificationStatus) {
      case 'pending':
        return <FiLoader className="w-16 h-16 text-[var(--color-primary)] mx-auto mb-4 animate-spin" />;
      case 'success':
        return <FiCheckCircle className="w-16 h-16 text-green-500 mx-auto mb-4" />;
      case 'error':
        return <FiXCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />;
      default:
        return <FiLoader className="w-16 h-16 text-[var(--color-primary)] mx-auto mb-4 animate-spin" />;
    }
  };

  const getStatusColor = () => {
    switch (verificationStatus) {
      case 'pending':
        return 'text-[var(--color-primary)]';
      case 'success':
        return 'text-green-500';
      case 'error':
        return 'text-red-500';
      default:
        return 'text-[var(--color-primary)]';
    }
  };

  const getStatusTitle = () => {
    switch (verificationStatus) {
      case 'pending':
        return 'Verifying Email...';
      case 'success':
        return 'Email Verified!';
      case 'error':
        return 'Verification Failed';
      default:
        return 'Verifying Email...';
    }
  };

  return (
    <>
      <Navbar />
      <div className="min-h-screen bg-[var(--color-bg)] pt-20 flex items-center justify-center px-4 py-8 sm:px-6 lg:px-8">
        <div className="w-full max-w-sm sm:max-w-md md:max-w-lg lg:max-w-md xl:max-w-md bg-[var(--color-card)] text-[var(--color-text-primary)] p-6 sm:p-8 rounded-2xl shadow-lg border border-[var(--color-border)]">
          
          {/* Header */}
          <div className="text-center mb-6">
            <h2 className="text-2xl sm:text-3xl font-bold text-[var(--color-primary)] mb-2">
              Email Verification
            </h2>
            <p className="text-sm text-[var(--color-text-secondary)]">
              Verifying your email address
            </p>
          </div>

          {/* Status Content */}
          <div className="text-center">
            {getStatusIcon()}
            
            <h3 className={`text-xl font-semibold mb-2 ${getStatusColor()}`}>
              {getStatusTitle()}
            </h3>
            
            <p className="text-[var(--color-text-secondary)] mb-6">
              {verificationMessage}
            </p>
            
            {verificationStatus === 'pending' && (
              <div className="w-full bg-[var(--color-input-bg)] rounded-full h-2 mb-6">
                <div className="bg-[var(--color-primary)] h-2 rounded-full animate-pulse" style={{ width: '60%' }}></div>
              </div>
            )}

            {verificationStatus === 'error' && (
              <div className="space-y-4">
                <button
                  onClick={() => navigate('/signup')}
                  className="w-full bg-[var(--color-primary)] text-white px-6 py-3 rounded-lg hover:opacity-90 transition-opacity font-semibold"
                >
                  Try Signing Up Again
                </button>
                
                <button
                  onClick={() => navigate('/login')}
                  className="w-full border border-[var(--color-border)] text-[var(--color-text-primary)] px-6 py-3 rounded-lg hover:bg-[var(--color-input-bg)] transition font-semibold"
                >
                  Go to Login
                </button>
              </div>
            )}

            {verificationStatus === 'success' && (
              <div className="space-y-4">
                <div className="text-sm text-[var(--color-text-secondary)] mb-4">
                  <p>Redirecting to your dashboard...</p>
                </div>
                <button
                  onClick={() => performSmartRedirect(navigate)}
                  className="w-full bg-[var(--color-primary)] text-white px-6 py-3 rounded-lg hover:opacity-90 transition-opacity font-semibold flex items-center justify-center"
                >
                  <FiArrowRight className="mr-2" />
                  Continue to App
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}

export default EmailVerificationCallback;