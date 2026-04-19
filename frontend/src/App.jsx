import { Routes, Route, useLocation } from 'react-router-dom';
import { lazy, Suspense, useEffect } from 'react';
import ProtectedRoute from './components/ProtectedRoute';
import IdleTimeoutModal from './components/IdleTimeoutModal';
import { useAuth } from './contexts/AuthContext';
import { useIdleTimeout } from './hooks/useIdleTimeout';
import './index.css';

// Lazy load heavy pages
const Landing             = lazy(() => import('./pages/Landing'));
const Signup              = lazy(() => import('./pages/SignUp'));
const Login               = lazy(() => import('./pages/Login'));
const ForgotPassword      = lazy(() => import('./pages/ForgotPassword'));
const ForgotUsername      = lazy(() => import('./pages/ForgotUsername'));
const ResetPassword       = lazy(() => import('./pages/ResetPassword'));
const VerifyEmail         = lazy(() => import('./pages/VerifyEmail'));
const UploadPage          = lazy(() => import('./pages/UploadPage'));
const ProfilePage         = lazy(() => import('./pages/ProfilePage'));
const DashboardPage       = lazy(() => import('./pages/DashboardPage'));
const QuestionsPage       = lazy(() => import('./pages/QuestionPage'));
const InterviewPage       = lazy(() => import('./pages/InterviewPage'));
const InterviewFeedbackPage = lazy(() => import('./pages/InterviewFeedbackPage'));
const PaymentSuccessPage  = lazy(() => import('./pages/PaymentSuccess'));
const FAQPage             = lazy(() => import('./pages/FAQPage'));
const AdminLogsPage       = lazy(() => import('./pages/AdminLogsPage'));
const SupportBot          = lazy(() => import('./components/SupportBot'));

const LoadingSpinner = () => (
  <div className="flex items-center justify-center min-h-screen">
    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
  </div>
);

function App() {
  const { logout, isAuthenticated } = useAuth();
  const location = useLocation();
  const isOnInterviewPage = location.pathname === '/interview';

  const { showWarning, timeRemaining, resetTimer } = useIdleTimeout(
    isOnInterviewPage ? null : 1440,
    30
  );

  const handleIdleLogout = () => {
    logout();
  };

  useEffect(() => {
    const prefetch = () => {
      import('./pages/UploadPage');
      import('./pages/DashboardPage');
      import('./pages/QuestionPage');
      import('./pages/InterviewPage');
      import('./components/SupportBot');
    };

    if (isAuthenticated) {
      if (typeof window !== 'undefined' && 'requestIdleCallback' in window) {
        const callbackId = window.requestIdleCallback(prefetch, { timeout: 1500 });
        return () => window.cancelIdleCallback?.(callbackId);
      }
      const timeoutId = window.setTimeout(prefetch, 750);
      return () => window.clearTimeout(timeoutId);
    }
  }, [isAuthenticated]);

  return (
    <>
      <Suspense fallback={<LoadingSpinner />}>
        <Routes>
          {/* Public routes */}
          <Route path="/"              element={<Landing />} />
          <Route path="/signup"        element={<Signup />} />
          <Route path="/login"         element={<Login />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/forgot-username" element={<ForgotUsername />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route path="/verify-email"  element={<VerifyEmail />} />
          <Route path="/faq"           element={<FAQPage />} />

          {/* Protected routes */}
          <Route path="/upload"        element={<ProtectedRoute><UploadPage /></ProtectedRoute>} />
          <Route path="/profile"       element={<ProtectedRoute><ProfilePage /></ProtectedRoute>} />
          <Route path="/dashboard"     element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
          <Route path="/questions"     element={<ProtectedRoute><QuestionsPage /></ProtectedRoute>} />
          <Route path="/payment-status" element={<ProtectedRoute><PaymentSuccessPage /></ProtectedRoute>} />
          <Route path="/interview"     element={<ProtectedRoute><InterviewPage /></ProtectedRoute>} />
          <Route path="/interview-feedback" element={<ProtectedRoute><InterviewFeedbackPage /></ProtectedRoute>} />
          <Route path="/admin/logs"    element={<ProtectedRoute><AdminLogsPage /></ProtectedRoute>} />
          <Route path="/admin/logs."   element={<ProtectedRoute><AdminLogsPage /></ProtectedRoute>} />
        </Routes>
      </Suspense>

      {isAuthenticated && !isOnInterviewPage && (
        <Suspense fallback={null}>
          <SupportBot />
        </Suspense>
      )}

      {!isOnInterviewPage && (
        <IdleTimeoutModal
          isOpen={showWarning}
          timeRemaining={timeRemaining}
          onStayLoggedIn={resetTimer}
          onLogout={handleIdleLogout}
        />
      )}
    </>
  );
}

export default App;
