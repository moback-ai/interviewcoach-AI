import { supabase } from '../supabaseClient';

/**
 * Validates if the current URL contains verification parameters
 */
export const hasVerificationParams = (searchParams) => {
  const accessToken = searchParams.get('access_token');
  const refreshToken = searchParams.get('refresh_token');
  const error = searchParams.get('error');
  const type = searchParams.get('type');
  
  return !!(accessToken || refreshToken || error || type);
};

/**
 * Extracts verification tokens from URL hash (fallback method)
 */
export const extractTokensFromHash = () => {
  const hash = window.location.hash;
  if (!hash) return null;
  
  try {
    const params = new URLSearchParams(hash.substring(1));
    const accessToken = params.get('access_token');
    const refreshToken = params.get('refresh_token');
    
    return accessToken && refreshToken ? { accessToken, refreshToken } : null;
  } catch (error) {
    console.error('Error extracting tokens from hash:', error);
    return null;
  }
};

/**
 * Validates email format
 */
export const isValidEmail = (email) => {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
};

/**
 * Formats error messages for better user experience
 */
export const formatErrorMessage = (error) => {
  if (typeof error === 'string') {
    return error;
  }
  
  if (error?.message) {
    // Handle common Supabase auth errors
    const message = error.message.toLowerCase();
    
    // Email validation errors
    if (message.includes('invalid email') || message.includes('email format')) {
      return 'Please enter a valid email address.';
    }
    if (message.includes('email required')) {
      return 'Email address is required.';
    }
    
    // Password validation errors
    if (message.includes('password') && message.includes('weak')) {
      return 'Password is too weak. Please choose a stronger password.';
    }
    if (message.includes('password') && message.includes('short')) {
      return 'Password is too short. Please use at least 8 characters.';
    }
    if (message.includes('password') && message.includes('requirements')) {
      return 'Password does not meet security requirements.';
    }
    
    // User registration errors
    if (message.includes('already registered') || message.includes('already exists')) {
      return 'This email is already registered. Please try logging in instead.';
    }
    if (message.includes('email not confirmed') || message.includes('not confirmed')) {
      return 'Please check your email and click the verification link.';
    }
    
    // Rate limiting and security errors
    if (message.includes('rate limit') || message.includes('too many requests')) {
      return 'Too many attempts. Please wait a moment before trying again.';
    }
    if (message.includes('expired')) {
      return 'The verification link has expired. Please request a new one.';
    }
    if (message.includes('invalid')) {
      return 'Invalid information provided. Please check your details.';
    }
    
    // Network and server errors
    if (message.includes('network') || message.includes('connection')) {
      return 'Network error. Please check your connection and try again.';
    }
    if (message.includes('server') || message.includes('service')) {
      return 'Service temporarily unavailable. Please try again later.';
    }
    
    // Return the original message if no specific case matches
    return error.message;
  }
  
  return 'An unexpected error occurred. Please try again.';
};

/**
 * Checks if user session is valid and email is confirmed
 */
export const isUserVerified = async () => {
  try {
    const { data: { session }, error } = await supabase.auth.getSession();
    
    if (error) {
      console.error('Session check error:', error);
      return false;
    }
    
    if (!session || !session.user) {
      return false;
    }
    
    // Check if email is confirmed
    return !!session.user.email_confirmed_at;
  } catch (error) {
    console.error('Error checking user verification:', error);
    return false;
  }
};

/**
 * Sends a resend verification email with proper error handling
 */
export const resendVerificationEmail = async (email) => {
  try {
    const { error } = await supabase.auth.resend({
      type: 'signup',
      email: email,
      options: {
        emailRedirectTo: `${window.location.origin}/auth/callback`
      }
    });

    if (error) {
      throw error;
    }

    return { success: true };
  } catch (error) {
    console.error('Resend verification error:', error);
    return { 
      success: false, 
      error: formatErrorMessage(error) 
    };
  }
};
