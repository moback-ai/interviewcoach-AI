import React, { useState, useEffect, useRef } from 'react';
import { supabase } from '../supabaseClient';
import { useNavigate, Link } from 'react-router-dom';
import { useTheme } from '../hooks/useTheme';
import { FiEye, FiEyeOff, FiMail, FiCheckCircle, FiLoader, FiX, FiFileText, FiShield, FiAlertCircle } from 'react-icons/fi';
import Navbar from '../components/Navbar';
import { isValidEmail, formatErrorMessage, resendVerificationEmail } from '../utils/emailVerificationUtils';
import { useSimpleVerificationStatus } from '../hooks/useSimpleVerificationStatus';
import { performSmartRedirect } from '../utils/smartRouting';
import { trackEvents } from '../services/mixpanel';
import { checkEmailAvailability } from '../utils/emailAvailability';

// Modal component for Terms & Conditions and Privacy Policy
const LegalModal = ({ isOpen, onClose, type }) => {
  const { theme } = useTheme();

  if (!isOpen) return null;

  const getContent = () => {
    if (type === 'terms') {
      return {
        title: 'Terms and Conditions',
        icon: <FiFileText className="w-8 h-8 text-[var(--color-primary)]" />,
        content: (
          <div className="space-y-4 text-sm leading-relaxed">
            <p>By using InterviewCoach, you agree to the following terms and conditions:</p>
            
            <div className="space-y-3">
              <div>
                <h4 className="font-semibold text-[var(--color-text-primary)]">1. Service Description</h4>
                <p>InterviewCoach provides AI-powered interview preparation services, including mock interviews, feedback, and coaching resources.</p>
              </div>
              
              <div>
                <h4 className="font-semibold text-[var(--color-text-primary)]">2. User Responsibilities</h4>
                <p>You are responsible for maintaining the confidentiality of your account and for all activities that occur under your account.</p>
              </div>
              
              <div>
                <h4 className="font-semibold text-[var(--color-text-primary)]">3. Acceptable Use</h4>
                <p>You agree not to use the service for any unlawful purpose or to transmit any harmful, offensive, or inappropriate content.</p>
              </div>
              
              <div>
                <h4 className="font-semibold text-[var(--color-text-primary)]">4. Intellectual Property</h4>
                <p>All content and materials available through InterviewCoach are protected by intellectual property rights.</p>
              </div>
              
              <div>
                <h4 className="font-semibold text-[var(--color-text-primary)]">5. Limitation of Liability</h4>
                <p>InterviewCoach is provided "as is" without warranties of any kind. We are not liable for any damages arising from your use of the service.</p>
              </div>
              
              <div>
                <h4 className="font-semibold text-[var(--color-text-primary)]">6. Termination</h4>
                <p>We reserve the right to terminate or suspend your account at any time for violations of these terms.</p>
              </div>
              
              <div>
                <h4 className="font-semibold text-[var(--color-text-primary)]">7. Changes to Terms</h4>
                <p>We may modify these terms at any time. Continued use of the service constitutes acceptance of any changes.</p>
              </div>
            </div>
            
            <p className="text-xs text-[var(--color-text-secondary)] mt-6">
              Last updated: {new Date().toLocaleDateString()}
            </p>
          </div>
        )
      };
    } else {
      return {
        title: 'Privacy Policy',
        icon: <FiShield className="w-8 h-8 text-[var(--color-primary)]" />,
        content: (
          <div className="space-y-4 text-sm leading-relaxed">
            <p>This Privacy Policy describes how InterviewCoach collects, uses, and protects your personal information.</p>
            
            <div className="space-y-3">
              <div>
                <h4 className="font-semibold text-[var(--color-text-primary)]">1. Information We Collect</h4>
                <p>We collect information you provide directly to us, such as your name, email address, and interview responses.</p>
              </div>
              
              <div>
                <h4 className="font-semibold text-[var(--color-text-primary)]">2. How We Use Your Information</h4>
                <p>We use your information to provide our services, improve our platform, and communicate with you about your account.</p>
              </div>
              
              <div>
                <h4 className="font-semibold text-[var(--color-text-primary)]">3. Information Sharing</h4>
                <p>We do not sell, trade, or otherwise transfer your personal information to third parties without your consent.</p>
              </div>
              
              <div>
                <h4 className="font-semibold text-[var(--color-text-primary)]">4. Data Security</h4>
                <p>We implement appropriate security measures to protect your personal information against unauthorized access or disclosure.</p>
              </div>
              
              <div>
                <h4 className="font-semibold text-[var(--color-text-primary)]">5. Your Rights</h4>
                <p>You have the right to access, update, or delete your personal information at any time.</p>
              </div>
              
              <div>
                <h4 className="font-semibold text-[var(--color-text-primary)]">6. Cookies and Tracking</h4>
                <p>We use cookies and similar technologies to enhance your experience and analyze usage patterns.</p>
              </div>
              
              <div>
                <h4 className="font-semibold text-[var(--color-text-primary)]">7. Contact Us</h4>
                <p>If you have questions about this Privacy Policy, please contact us at privacy@interviewcoach.com</p>
              </div>
            </div>
            
            <p className="text-xs text-[var(--color-text-secondary)] mt-6">
              Last updated: {new Date().toLocaleDateString()}
            </p>
          </div>
        )
      };
    }
  };

  const { title, icon, content } = getContent();

  return (
    <div 
      className="fixed inset-0 bg-black bg-opacity-0 flex items-center justify-center z-50 p-4 transition-all duration-300 ease-out"
      style={{ backgroundColor: isOpen ? 'rgba(0, 0, 0, 0.5)' : 'rgba(0, 0, 0, 0)' }}
      onClick={onClose}
    >
      <div 
        className={`bg-[var(--color-card)] rounded-2xl shadow-xl max-w-2xl w-full max-h-[90vh] overflow-hidden transform transition-all duration-300 ease-out ${
          isOpen ? 'scale-100 opacity-100 translate-y-0' : 'scale-95 opacity-0 translate-y-4'
        }`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-6 border-b border-[var(--color-border)]">
          <div className="flex items-center space-x-3">
            <div className="transform transition-transform duration-200 hover:scale-110">
              {icon}
            </div>
            <h2 className="text-xl font-bold text-[var(--color-text-primary)]">{title}</h2>
          </div>
          <button
            onClick={onClose}
            className="text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] transition-all duration-200 hover:scale-110 p-1 rounded-full hover:bg-[var(--color-input-bg)] cursor-pointer"
          >
            <FiX className="w-6 h-6" />
          </button>
        </div>
        
        <div className="p-6 overflow-y-auto max-h-[calc(90vh-120px)] scrollbar-thin scrollbar-thumb-[var(--color-border)] scrollbar-track-transparent">
          {content}
        </div>
      </div>
    </div>
  );
};

function Signup() {
  const navigate = useNavigate();
  const { theme } = useTheme();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [errorMsg, setErrorMsg] = useState('');
  const [successMsg, setSuccessMsg] = useState('');
  const [loading, setLoading] = useState(false);
  const [passwordVisible, setPasswordVisible] = useState(false);
  const [showVerificationMessage, setShowVerificationMessage] = useState(false);
  const [acceptedTerms, setAcceptedTerms] = useState(false);
  const [showLegalModal, setShowLegalModal] = useState(false);
  const [legalModalType, setLegalModalType] = useState('terms');
  
  // Email validation states
  const [emailChecking, setEmailChecking] = useState(false);
  const [emailAvailable, setEmailAvailable] = useState(null); // null = not checked, true = available, false = taken
  const [emailTouched, setEmailTouched] = useState(false);
  const emailCheckTimeoutRef = useRef(null);

  // Use the simplified verification status hook (big tech approach)
  const { isChecking, checkVerificationStatus } = useSimpleVerificationStatus(email, showVerificationMessage);

  // Compute form validity - standard practice
  // Email must be available (or not checked yet) to allow signup
  const isFormValid = fullName.trim() && email.trim() && password.trim() && acceptedTerms && emailAvailable !== false;

  const openLegalModal = (type) => {
    setLegalModalType(type);
    setShowLegalModal(true);
  };

  const closeLegalModal = () => {
    setShowLegalModal(false);
  };

  // Handle email input change with debouncing
  const handleEmailChange = (e) => {
    const newEmail = e.target.value;
    setEmail(newEmail);
    setEmailTouched(true);
    
    // Reset availability state when email changes
    if (emailAvailable !== null) {
      setEmailAvailable(null);
    }
    
    // Clear existing timeout
    if (emailCheckTimeoutRef.current) {
      clearTimeout(emailCheckTimeoutRef.current);
    }
    
    // Only check if email looks valid
    if (newEmail.trim() && isValidEmail(newEmail.trim())) {
      // Debounce: wait 500ms after user stops typing
      emailCheckTimeoutRef.current = setTimeout(() => {
        checkEmail(newEmail.trim());
      }, 500);
    }
  };

  // Handle email blur - check immediately when user leaves field
  const handleEmailBlur = () => {
    setEmailTouched(true);
    
    // Clear any pending timeout
    if (emailCheckTimeoutRef.current) {
      clearTimeout(emailCheckTimeoutRef.current);
    }
    
    // Check email if it's valid and hasn't been checked yet
    if (email.trim() && isValidEmail(email.trim()) && emailAvailable === null) {
      checkEmail(email.trim());
    }
  };

  // Check email availability
  const checkEmail = async (emailToCheck) => {
    if (!emailToCheck || !isValidEmail(emailToCheck)) {
      setEmailAvailable(null);
      return;
    }

    setEmailChecking(true);
    try {
      const result = await checkEmailAvailability(emailToCheck);
      setEmailAvailable(result.available);
      
      if (!result.available) {
        setErrorMsg('This email is already registered. Please try logging in instead or use the "Forgot Password" option if you don\'t remember your password.');
      } else {
        // Clear error if email becomes available
        if (errorMsg.includes('already registered')) {
          setErrorMsg('');
        }
      }
    } catch (error) {
      console.error('Error checking email:', error);
      // Fail open - don't block signup if check fails
      setEmailAvailable(null);
    } finally {
      setEmailChecking(false);
    }
  };

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (emailCheckTimeoutRef.current) {
        clearTimeout(emailCheckTimeoutRef.current);
      }
    };
  }, []);

  const handleSignup = async (e) => {
    e.preventDefault();
    setLoading(true);
    setErrorMsg('');
    setSuccessMsg('');

    if (!acceptedTerms) {
      setErrorMsg('You must accept the Terms and Conditions and Privacy Policy to continue.');
      setLoading(false);
      return;
    }

    // Final check: Ensure email is available before attempting signup
    if (emailAvailable === false) {
      setErrorMsg('This email is already registered. Please try logging in instead or use the "Forgot Password" option if you don\'t remember your password.');
      setLoading(false);
      return;
    }

    // If email hasn't been checked yet, check it now
    if (emailAvailable === null && email.trim() && isValidEmail(email.trim())) {
      const result = await checkEmailAvailability(email.trim());
      if (!result.available) {
        setErrorMsg('This email is already registered. Please try logging in instead or use the "Forgot Password" option if you don\'t remember your password.');
        setLoading(false);
        return;
      }
      setEmailAvailable(true);
    }

    try {
      // Attempt signup (Supabase will reject if email exists)
      const { data, error } = await supabase.auth.signUp({
        email: email.toLowerCase().trim(),
        password,
        options: {
          data: {
            full_name: fullName.trim()
          },
          emailRedirectTo: `${window.location.origin}/auth/callback`
        }
      });

      if (error) {
        // Handle specific error cases
        const errorMessage = error.message.toLowerCase();
        
        if (errorMessage.includes('already registered') || 
            errorMessage.includes('already exists') ||
            errorMessage.includes('user already registered') ||
            error.code === 'signup_disabled') {
          setErrorMsg('This email is already registered. Please try logging in instead or use the "Forgot Password" option if you don\'t remember your password.');
          return;
        }
        
        setErrorMsg(formatErrorMessage(error));
      } else {
        // Check if user was actually created (might return user even if email exists in some cases)
        if (data.user) {
          setShowVerificationMessage(true);
          setSuccessMsg('Account created successfully! Please check your email to verify your account and complete the signup process.');
          
          // Track successful sign up with user data
          trackEvents.signUp({
            email: email,
            user_id: data.user?.id,
            full_name: fullName.trim(),
            signup_timestamp: new Date().toISOString()
          });
        } else {
          // User might already exist but Supabase returned success
          setErrorMsg('This email may already be registered. Please try logging in instead.');
        }
      }
    } catch (err) {
      console.error(err);
      setErrorMsg('Something went wrong. Please try again later.');
    } finally {
      setLoading(false);
    }
  };

  const handlePasswordVisibilityToggle = () => {
    setPasswordVisible(!passwordVisible);
  };

  const handleResendVerification = async () => {
    setLoading(true);
    setErrorMsg('');
    
    const result = await resendVerificationEmail(email);
    
    if (result.success) {
      setSuccessMsg('Verification email sent again! Please check your inbox.');
    } else {
      setErrorMsg(result.error);
    }
    
    setLoading(false);
  };

  const handleManualCheck = async () => {
    setErrorMsg('');
    const isVerified = await checkVerificationStatus();
    if (isVerified) {
      setSuccessMsg('Email verified successfully! Redirecting to your dashboard...');
      setTimeout(() => {
        performSmartRedirect(navigate);
      }, 2000);
    } else {
      setErrorMsg('Email not verified yet. Please check your email and click the verification link.');
    }
  };

  if (showVerificationMessage) {
    const getStatusIcon = () => {
      return isChecking ? (
        <FiLoader className="w-16 h-16 text-blue-500 mx-auto mb-4 animate-spin" />
      ) : (
        <FiMail className="w-16 h-16 text-[var(--color-primary)] mx-auto mb-4" />
      );
    };

    return (
      <>
        <Navbar />
        <div className="min-h-screen flex items-center justify-center bg-[var(--color-bg)] px-4 py-8 sm:px-6 lg:px-8">
          <div className="w-full max-w-md bg-[var(--color-card)] text-[var(--color-text-primary)] p-8 rounded-2xl shadow-lg border border-[var(--color-border)] text-center">
                         <div className="mb-6">
               {getStatusIcon()}
               <h2 className="text-2xl font-bold mb-2 text-[var(--color-primary)]">
                 Check Your Email
               </h2>
               <p className="text-[var(--color-text-secondary)]">
                 We've sent a verification link to:
               </p>
               <p className="font-semibold text-[var(--color-text-primary)] mt-2">
                 {email}
               </p>
               {isChecking && (
                 <p className="text-sm text-blue-500 mt-2">
                   Checking verification status...
                 </p>
               )}
             </div>

            {errorMsg && (
              <div className="mb-4 p-3 rounded-lg bg-red-50 border border-red-200 text-center">
                <p className="text-[var(--color-error)] text-sm font-medium">{errorMsg}</p>
              </div>
            )}
            {successMsg && (
              <div className="mb-4 p-3 rounded-lg bg-green-50 border border-green-200 text-center">
                <p className="text-green-700 text-sm font-medium">{successMsg}</p>
              </div>
            )}

                         <div className="space-y-4">
               <button
                 onClick={handleResendVerification}
                 disabled={loading}
                 className={`w-full py-2 px-4 font-semibold rounded text-white transition ${
                   loading
                     ? 'bg-gray-400 cursor-not-allowed'
                     : 'bg-[var(--color-primary)] hover:opacity-90'
                 }`}
               >
                 {loading ? 'Sending...' : 'Resend Verification Email'}
               </button>

               <button
                 onClick={handleManualCheck}
                 disabled={isChecking}
                 className={`w-full py-2 px-4 font-semibold rounded border border-[var(--color-primary)] text-[var(--color-primary)] hover:bg-[var(--color-primary)] hover:text-white transition ${
                   isChecking ? 'opacity-50 cursor-not-allowed' : ''
                 }`}
               >
                 {isChecking ? 'Checking...' : 'Check Verification Status'}
               </button>

               <button
                 onClick={() => navigate('/login')}
                 className="w-full py-2 px-4 font-semibold rounded border border-[var(--color-border)] text-[var(--color-text-primary)] hover:bg-[var(--color-input-bg)] transition"
               >
                 Go to Login
               </button>
             </div>

                         <div className="mt-6 space-y-3">
               <p className="text-sm text-[var(--color-text-secondary)]">
                 Didn't receive the email? Check your spam folder or{' '}
                 <button
                   onClick={handleResendVerification}
                   className="text-[var(--color-primary)] hover:underline"
                 >
                   try again
                 </button>
               </p>
               <p className="text-xs text-[var(--color-text-secondary)]">
                 After verification, you'll be automatically logged in and redirected to start using InterviewCoach.
               </p>
             </div>
          </div>
        </div>
        
        <LegalModal
          isOpen={showLegalModal}
          onClose={closeLegalModal}
          type={legalModalType}
        />
      </>
    );
  }

  return (
    <>
      <Navbar />
      <div className="min-h-screen flex items-center justify-center bg-[var(--color-bg)] px-4 py-8 sm:px-6 lg:px-8">
        <div className="w-full max-w-sm sm:max-w-md md:max-w-lg lg:max-w-md xl:max-w-md bg-[var(--color-card)] text-[var(--color-text-primary)] p-6 sm:p-8 rounded-2xl shadow-lg border border-[var(--color-border)]">
          <h2 className="text-2xl sm:text-3xl font-bold text-center mb-6 text-[var(--color-primary)]">
            Create an Account
          </h2>

          {errorMsg && (
            <div className="mb-4 p-3 rounded-lg bg-red-50 border border-red-200 text-center">
              <p className="text-[var(--color-error)] text-sm font-medium">{errorMsg}</p>
            </div>
          )}
          {successMsg && (
            <div className="mb-4 p-3 rounded-lg bg-green-50 border border-green-200 text-center">
              <p className="text-green-700 text-sm font-medium">{successMsg}</p>
            </div>
          )}

          <form onSubmit={handleSignup} className="space-y-5" aria-label="Signup Form">
            {/* Full Name */}
            <div>
              <label htmlFor="fullName" className="block text-sm font-medium mb-1 text-[var(--color-text-secondary)]">
                Full Name
              </label>
              <input
                id="fullName"
                type="text"
                autoComplete="name"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                required
                disabled={loading}
                className="w-full px-4 py-2 rounded-lg bg-[var(--color-input-bg)] text-[var(--color-text-primary)] border border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] transition"
              />
            </div>

            {/* Email */}
            <div>
              <label htmlFor="email" className="block text-sm font-medium mb-1 text-[var(--color-text-secondary)]">
                Email
              </label>
              <div className="relative">
                <input
                  id="email"
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={handleEmailChange}
                  onBlur={handleEmailBlur}
                  required
                  disabled={loading}
                  className={`w-full px-4 py-2 pr-10 rounded-lg bg-[var(--color-input-bg)] text-[var(--color-text-primary)] border transition ${
                    emailTouched && email.trim()
                      ? emailAvailable === false
                        ? 'border-red-500 focus:ring-2 focus:ring-red-500'
                        : emailAvailable === true
                        ? 'border-green-500 focus:ring-2 focus:ring-green-500'
                        : 'border-[var(--color-border)] focus:ring-2 focus:ring-[var(--color-primary)]'
                      : 'border-[var(--color-border)] focus:ring-2 focus:ring-[var(--color-primary)]'
                  } focus:outline-none`}
                />
                {/* Email validation icon */}
                <div className="absolute right-3 top-1/2 transform -translate-y-1/2">
                  {emailChecking ? (
                    <FiLoader className="w-5 h-5 text-blue-500 animate-spin" />
                  ) : emailTouched && email.trim() && isValidEmail(email.trim()) ? (
                    emailAvailable === true ? (
                      <FiCheckCircle className="w-5 h-5 text-green-500" />
                    ) : emailAvailable === false ? (
                      <FiAlertCircle className="w-5 h-5 text-red-500" />
                    ) : null
                  ) : null}
                </div>
              </div>
              {/* Email availability message - only show error, not success */}
              {emailTouched && email.trim() && isValidEmail(email.trim()) && !emailChecking && emailAvailable === false && (
                <div className="mt-1 text-xs">
                  <p className="text-red-600 dark:text-red-400 flex items-center gap-1">
                    <FiAlertCircle className="w-3 h-3" />
                    This email is already registered. <Link to="/login" className="underline font-medium">Login instead?</Link>
                  </p>
                </div>
              )}
            </div>

            {/* Password */}
            <div>
              <label htmlFor="password" className="block text-sm font-medium mb-1 text-[var(--color-text-secondary)]">
                Password
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={passwordVisible ? 'text' : 'password'}
                  autoComplete="new-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  disabled={loading}
                  className="w-full px-4 py-2 rounded-lg bg-[var(--color-input-bg)] text-[var(--color-text-primary)] border border-[var(--color-border)] focus:ring-2 focus:ring-[var(--color-primary)] transition"
                />
                <button
                  type="button"
                  onClick={handlePasswordVisibilityToggle}
                  className="absolute right-3 top-1/2 transform -translate-y-1/2 text-[var(--color-text-secondary)] hover:text-[var(--color-primary)] cursor-pointer"
                  aria-label="Toggle password visibility"
                >
                  {passwordVisible ? <FiEyeOff className="w-5 h-5" /> : <FiEye className="w-5 h-5" />}
                </button>
              </div>
            </div>

            {/* Terms and Conditions Checkbox */}
            <div className="flex items-center">
              <input
                type="checkbox"
                id="terms"
                checked={acceptedTerms}
                onChange={(e) => setAcceptedTerms(e.target.checked)}
                required
                className="mr-2 h-4 w-4 text-[var(--color-primary)] focus:ring-blue-500 border-gray-300 rounded"
              />
              <label htmlFor="terms" className="text-sm text-[var(--color-text-secondary)]">
                I agree to the{' '}
                <button
                  type="button"
                  onClick={() => openLegalModal('terms')}
                  className="text-[var(--color-primary)] hover:underline cursor-pointer"
                >
                  Terms and Conditions
                </button>{' '}
                and{' '}
                <button
                  type="button"
                  onClick={() => openLegalModal('privacy')}
                  className="text-[var(--color-primary)] hover:underline cursor-pointer"
                >
                  Privacy Policy
                </button>
              </label>
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={loading || !isFormValid}
              className={`w-full py-2 font-semibold rounded text-white transition ${
                loading || !isFormValid
                  ? 'bg-gray-400 cursor-not-allowed opacity-60'
                  : 'bg-[var(--color-primary)] hover:opacity-90'
              }`}
            >
              {loading ? 'Creating account...' : 'Sign Up'}
            </button>
          </form>

          {/* Login Link */}
          <p className="mt-6 text-sm text-center text-[var(--color-text-secondary)]">
            Already have an account?{' '}
            <Link to="/login" className="text-[var(--color-primary)] hover:underline">
              Login
            </Link>
          </p>
        </div>
      </div>

      <LegalModal
        isOpen={showLegalModal}
        onClose={closeLegalModal}
        type={legalModalType}
      />
    </>
  );
}

export default Signup;