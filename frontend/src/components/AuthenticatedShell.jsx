import { Outlet, useLocation } from 'react-router-dom';
import { lazy, Suspense, useEffect } from 'react';
import ProtectedRoute from './ProtectedRoute';
import IdleTimeoutModal from './IdleTimeoutModal';
import { useAuth } from '../contexts/AuthContext';
import { useIdleTimeout } from '../hooks/useIdleTimeout';

const SupportBot = lazy(() => import('./SupportBot'));

function AuthenticatedShell() {
  const { logout } = useAuth();
  const location = useLocation();
  const isOnInterviewPage = location.pathname === '/interview';

  const { showWarning, timeRemaining, resetTimer } = useIdleTimeout(
    isOnInterviewPage ? null : 1440,
    30
  );

  useEffect(() => {
    const verifySession = async () => {
      try {
        const { apiGet } = await import('../api');
        await apiGet('/api/me');
      } catch {
        // The auth interceptor handles redirecting on invalid sessions.
      }
    };

    if (!isOnInterviewPage) {
      verifySession();
    }
  }, [location.pathname, isOnInterviewPage]);

  const handleIdleLogout = () => {
    logout();
  };

  return (
    <ProtectedRoute>
      <>
        <Outlet />
        {!isOnInterviewPage && (
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
    </ProtectedRoute>
  );
}

export default AuthenticatedShell;
