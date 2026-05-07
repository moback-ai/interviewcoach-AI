import { clearStoredAuth } from '../lib/authClient';

const AUTH_API_ROUTES = ['/api/login', '/api/signup', '/api/verify-email'];
const AUTH_PAGES = new Set(['/login', '/signup', '/forgot-password', '/forgot-username', '/reset-password', '/verify-email']);

const getCurrentPath = () => `${window.location.pathname}${window.location.search}${window.location.hash}`;

export const redirectToLogin = ({ expired = false, nextPath = '' } = {}) => {
  clearStoredAuth();

  if (typeof window === 'undefined') {
    return;
  }

  const params = new URLSearchParams();
  if (expired) {
    params.set('expired', 'true');
  }
  if (nextPath && nextPath.startsWith('/')) {
    params.set('next', nextPath);
  }

  const target = `/login${params.toString() ? `?${params.toString()}` : ''}`;
  if (getCurrentPath() !== target) {
    window.location.replace(target);
  }
};

export const initAuthInterceptor = () => {
  if (typeof window === 'undefined' || window.__icAuthInterceptorInitialized) {
    return;
  }

  const originalFetch = window.fetch.bind(window);

  window.fetch = async (...args) => {
    const response = await originalFetch(...args);

    if (response.status === 401) {
      const url = args[0] ? args[0].toString() : '';
      const options = args[1] || {};
      const isAuthEndpoint = AUTH_API_ROUTES.some((route) => url.includes(route));
      const isAuthPage = AUTH_PAGES.has(window.location.pathname);
      const isHandledLocally = Boolean(options.authRedirectHandled);

      if (!isAuthEndpoint && !isAuthPage && !isHandledLocally) {
        const currentPath = getCurrentPath();
        window.setTimeout(() => {
          redirectToLogin({ expired: true, nextPath: currentPath });
        }, 100);
      }
    }

    return response;
  };

  window.__icAuthInterceptorInitialized = true;
};
