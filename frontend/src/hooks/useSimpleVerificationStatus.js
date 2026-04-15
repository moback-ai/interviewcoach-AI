import { useState } from 'react';
import { supabase } from '../supabaseClient';

export const useSimpleVerificationStatus = (email, isVerificationPending = false) => {
  const [isChecking, setIsChecking] = useState(false);

  const checkVerificationStatus = async () => {
    setIsChecking(true);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (session?.user?.email_confirmed_at && session.user.email === email) {
        return true;
      }
      return false;
    } catch (error) {
      console.error('Error checking verification status:', error);
      return false;
    } finally {
      setIsChecking(false);
    }
  };

  return {
    isChecking,
    checkVerificationStatus
  };
};
