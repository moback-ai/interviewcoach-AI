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

  window.__icAuthInterceptorInitialized = true;

  // Do not patch fetch to auto-redirect on 401.
  // api.js handles refresh + retry; a global redirect raced refresh-token and
  // kicked users off mid-interview (e.g. transcribe-audio).
};
