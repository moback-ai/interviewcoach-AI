import { Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import { lazy, Suspense, useEffect } from 'react';
import Landing from './pages/Landing';
import Signup from './pages/SignUp';
import Login from './pages/Login';
import ProtectedRoute from './components/ProtectedRoute';
import SupportBot from './components/SupportBot';
import IdleTimeoutModal from './components/IdleTimeoutModal';
import { useAuth } from './contexts/AuthContext';
import { useIdleTimeout } from './hooks/useIdleTimeout';
import './index.css';

// Lazy load heavy pages
const UploadPage          = lazy(() => import('./pages/UploadPage'));
const ProfilePage         = lazy(() => import('./pages/ProfilePage'));
const DashboardPage       = lazy(() => import('./pages/DashboardPage'));
const QuestionsPage       = lazy(() => import('./pages/QuestionPage'));
const InterviewPage       = lazy(() => import('./pages/InterviewPage'));
const InterviewFeedbackPage = lazy(() => import('./pages/InterviewFeedbackPage'));
const FAQPage             = lazy(() => import('./pages/FAQPage'));

const LoadingSpinner = () => (
  <div className="flex items-center justify-center min-h-screen">
    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
  </div>
);

function App() {
  const { logout } = useAuth();
  const location = useLocation();
  const isOnInterviewPage = location.pathname === '/interview';

  const { showWarning, timeRemaining, resetTimer } = useIdleTimeout(
    isOnInterviewPage ? null : 1440,
    30
  );

  const handleIdleLogout = () => {
    logout();
  };

  return (
    <>
      <Suspense fallback={<LoadingSpinner />}>
        <Routes>
          {/* Public routes */}
          <Route path="/"              element={<Landing />} />
          <Route path="/signup"        element={<Signup />} />
          <Route path="/login"         element={<Login />} />
          <Route path="/faq"           element={<FAQPage />} />

          {/* Protected routes */}
          <Route path="/upload"        element={<ProtectedRoute><UploadPage /></ProtectedRoute>} />
          <Route path="/profile"       element={<ProtectedRoute><ProfilePage /></ProtectedRoute>} />
          <Route path="/dashboard"     element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
          <Route path="/questions"     element={<ProtectedRoute><QuestionsPage /></ProtectedRoute>} />
          <Route path="/interview"     element={<ProtectedRoute><InterviewPage /></ProtectedRoute>} />
          <Route path="/interview-feedback" element={<ProtectedRoute><InterviewFeedbackPage /></ProtectedRoute>} />
        </Routes>
      </Suspense>

      <SupportBot />

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
