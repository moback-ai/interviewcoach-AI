import { clearStoredAuth } from '../lib/authClient';

const AUTH_BYPASS_MARKERS = [
  '/api/login',
  '/api/signup',
  '/api/verify-email',
  '/api/resend-verification',
  '/api/forgot-password',
  '/api/forgot-username',
  '/api/reset-password',
];

const AUTH_ERROR_MARKERS = [
  '401',
  'token',
  'unauthorized',
  'authorization',
  'session expired',
  'invalid token',
];

const buildExpiredLoginUrl = () => {
  const params = new URLSearchParams();
  params.set('expired', 'true');

  const nextPath = `${window.location.pathname}${window.location.search}`.trim();
  if (nextPath && nextPath !== '/' && !nextPath.startsWith('/login')) {
    params.set('next', nextPath);
  }

  return `/login?${params.toString()}`;
};

export const isAuthErrorMessage = (message = '') => {
  const normalized = String(message || '').toLowerCase();
  return AUTH_ERROR_MARKERS.some((marker) => normalized.includes(marker));
};

export const redirectToExpiredLogin = () => {
  clearStoredAuth();

  if (window.location.pathname === '/login') {
    return;
  }

  window.location.assign(buildExpiredLoginUrl());
};

export const initAuthInterceptor = () => {
  if (window.__icAuthInterceptorInitialized) {
    return;
  }

  const originalFetch = window.fetch.bind(window);
  window.__icAuthInterceptorInitialized = true;

  window.fetch = async (...args) => {
    const response = await originalFetch(...args);

    if (response.status === 401) {
      const requestUrl = args[0] ? args[0].toString() : '';
      const isBypassedAuthRequest = AUTH_BYPASS_MARKERS.some((marker) => requestUrl.includes(marker));

      if (!isBypassedAuthRequest) {
        console.warn('[AuthInterceptor] 401 detected on protected request. Clearing session.');
        window.setTimeout(() => {
          redirectToExpiredLogin();
        }, 100);
      }
    }

    return response;
  };
};
