import { Routes, Route } from 'react-router-dom';
import { lazy, Suspense } from 'react';
import './index.css';

// Lazy load heavy pages
const Landing             = lazy(() => import('./pages/Landing'));
const Signup              = lazy(() => import('./pages/SignUp'));
const Login               = lazy(() => import('./pages/Login'));
const ForgotPassword      = lazy(() => import('./pages/ForgotPassword'));
const ForgotUsername      = lazy(() => import('./pages/ForgotUsername'));
const ResetPassword       = lazy(() => import('./pages/ResetPassword'));
const VerifyEmail         = lazy(() => import('./pages/VerifyEmail'));
const AuthenticatedShell  = lazy(() => import('./components/AuthenticatedShell'));
const UploadPage          = lazy(() => import('./pages/UploadPage'));
const ProfilePage         = lazy(() => import('./pages/ProfilePage'));
const DashboardPage       = lazy(() => import('./pages/DashboardPage'));
const QuestionsPage       = lazy(() => import('./pages/QuestionPage'));
const InterviewPage       = lazy(() => import('./pages/InterviewPage'));
const InterviewFeedbackPage = lazy(() => import('./pages/InterviewFeedbackPage'));
const PaymentSuccessPage  = lazy(() => import('./pages/PaymentSuccess'));
const FAQPage             = lazy(() => import('./pages/FAQPage'));
const AdminLogsPage       = lazy(() => import('./pages/AdminLogsPage'));

const LoadingSpinner = () => (
  <div className="flex items-center justify-center min-h-screen">
    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
  </div>
);

function App() {
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
          <Route element={<AuthenticatedShell />}>
            <Route path="/upload"        element={<UploadPage />} />
            <Route path="/profile"       element={<ProfilePage />} />
            <Route path="/dashboard"     element={<DashboardPage />} />
            <Route path="/questions"     element={<QuestionsPage />} />
            <Route path="/payment-status" element={<PaymentSuccessPage />} />
            <Route path="/interview"     element={<InterviewPage />} />
            <Route path="/interview-feedback" element={<InterviewFeedbackPage />} />
            <Route path="/admin/logs"    element={<AdminLogsPage />} />
            <Route path="/admin/logs."   element={<AdminLogsPage />} />
          </Route>
        </Routes>
      </Suspense>
    </>
  );
}

export default App;
