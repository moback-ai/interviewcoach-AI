import { Outlet, useLocation } from 'react-router-dom';
import { lazy, Suspense, useEffect } from 'react';
import ProtectedRoute from './ProtectedRoute';
import IdleTimeoutModal from './IdleTimeoutModal';
import { useAuth } from '../contexts/AuthContext';
import { useIdleTimeout } from '../hooks/useIdleTimeout';
import { useTheme } from '../hooks/useTheme';
import { unlockBodyScroll } from '../utils/unlockBodyScroll';

const SupportBot = lazy(() => import('./SupportBot'));

function AuthenticatedShell() {
  // Syncs `html.dark` from localStorage for every protected route — needed when
  // `/interview` is cold-loaded (e.g. dashboard Resume uses full page navigation)
  // and no Navbar/ThemeToggle mounts before the interview UI.
  useTheme();

  const { logout } = useAuth();
  const location = useLocation();
  const isOnInterviewPage = location.pathname === '/interview';

  const { showWarning, timeRemaining, resetTimer } = useIdleTimeout(10, 30);

  useEffect(() => {
    unlockBodyScroll();
  }, [location.pathname]);

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
    logout({ expired: true });
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
        <IdleTimeoutModal
          isOpen={showWarning}
          timeRemaining={timeRemaining}
          onStayLoggedIn={resetTimer}
          onLogout={handleIdleLogout}
        />
      </>
    </ProtectedRoute>
  );
}

export default AuthenticatedShell;