import { useState, useEffect, useCallback } from 'react';
import { supabase } from '../supabaseClient';
import { extractTokensFromHash, formatErrorMessage } from '../utils/emailVerificationUtils';

export const useEmailVerification = () => {
  const [verificationStatus, setVerificationStatus] = useState('idle'); // 'idle', 'pending', 'success', 'error'
  const [verificationMessage, setVerificationMessage] = useState('');

  const handleEmailVerification = useCallback(async (searchParams) => {
    setVerificationStatus('pending');
    
    try {
      const accessToken = searchParams.get('access_token');
      const refreshToken = searchParams.get('refresh_token');
      const error = searchParams.get('error');
      const errorDescription = searchParams.get('error_description');

      if (error) {
        setVerificationStatus('error');
        setVerificationMessage(formatErrorMessage(errorDescription || 'Email verification failed'));
        return { success: false, error: errorDescription };
      }

      if (accessToken && refreshToken) {
        // Set the session with the tokens from the URL
        const { data, error: sessionError } = await supabase.auth.setSession({
          access_token: accessToken,
          refresh_token: refreshToken,
        });

        if (sessionError) {
          setVerificationStatus('error');
          setVerificationMessage(formatErrorMessage(sessionError));
          return { success: false, error: sessionError.message };
        } else {
          setVerificationStatus('success');
          setVerificationMessage('Email verified successfully! Welcome to InterviewCoach.');
          return { success: true, email: data.session?.user?.email, user_id: data.session?.user?.id };
        }
      } else {
        // Handle the case where user clicks the verification link
        const { data: { session }, error: sessionError } = await supabase.auth.getSession();
        
        if (sessionError) {
          setVerificationStatus('error');
          setVerificationMessage(formatErrorMessage(sessionError));
          return { success: false, error: sessionError.message };
        } else if (session && session.user) {
          if (session.user.email_confirmed_at) {
            setVerificationStatus('success');
            setVerificationMessage('Email verified successfully! Welcome to InterviewCoach.');
            return { success: true, email: session.user.email, user_id: session.user.id };
          } else {
            setVerificationStatus('error');
            setVerificationMessage('Email verification is still pending. Please check your email and click the verification link.');
            return { success: false, error: 'Email not confirmed' };
          }
        } else {
          // Try to handle the verification manually from hash
          const tokens = extractTokensFromHash();
          
          if (tokens) {
            const { data, error } = await supabase.auth.setSession({
              access_token: tokens.accessToken,
              refresh_token: tokens.refreshToken,
            });
            
            if (error) {
              setVerificationStatus('error');
              setVerificationMessage(formatErrorMessage(error));
              return { success: false, error: error.message };
                    } else {
          setVerificationStatus('success');
          setVerificationMessage('Email verified successfully! Welcome to InterviewCoach.');
          return { success: true, email: data.session?.user?.email, user_id: data.session?.user?.id };
        }
          } else {
            setVerificationStatus('error');
            setVerificationMessage('Verification link is invalid or has expired. Please try signing up again.');
            return { success: false, error: 'Invalid verification link' };
          }
        }
      }
    } catch (err) {
      console.error('Email verification error:', err);
      setVerificationStatus('error');
      setVerificationMessage('An unexpected error occurred');
      return { success: false, error: err.message };
    }
  }, []); // Empty dependency array since the function doesn't depend on any external values

  const resetVerification = () => {
    setVerificationStatus('idle');
    setVerificationMessage('');
  };

  return {
    verificationStatus,
    verificationMessage,
    handleEmailVerification,
    resetVerification
  };
};
