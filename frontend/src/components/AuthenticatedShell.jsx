import { Outlet, useLocation } from 'react-router-dom';
import { lazy, Suspense } from 'react';
import ProtectedRoute from './ProtectedRoute';
import IdleTimeoutModal from './IdleTimeoutModal';
import { useAuth } from '../contexts/AuthContext';
import { useIdleTimeout } from '../hooks/useIdleTimeout';
import { useTheme } from '../hooks/useTheme';

const SupportBot = lazy(() => import('./SupportBot'));

function AuthenticatedShell() {
  // Syncs `html.dark` from localStorage for every protected route — needed when
  // `/interview` is cold-loaded (e.g. dashboard Resume uses full page navigation)
  // and no Navbar/ThemeToggle mounts before the interview UI.
  useTheme();

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