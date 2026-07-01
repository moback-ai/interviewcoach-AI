const LOCAL_HOSTS = new Set(['localhost', '127.0.0.1']);

/** Production apex hostname (without www). Override via VITE_APEX_DOMAIN at build time. */
const APEX_DOMAIN = (import.meta.env.VITE_APEX_DOMAIN || 'ugaanlabs.ai').toLowerCase();
const CANONICAL_HOST = (import.meta.env.VITE_CANONICAL_HOST || `www.${APEX_DOMAIN}`).toLowerCase();

function isLocalHost(hostname) {
  return LOCAL_HOSTS.has(hostname);
}

function buildCanonicalHref(pathname, search, hash) {
  return `https://${CANONICAL_HOST}${pathname || '/'}${search || ''}${hash || ''}`;
}

/**
 * Redirect apex or plain-http production traffic to https://www before the SPA loads.
 * Returns true when a redirect was triggered.
 */
export function enforceCanonicalOrigin() {
  if (typeof window === 'undefined') {
    return false;
  }

  const { hostname, protocol, pathname, search, hash } = window.location;
  if (isLocalHost(hostname)) {
    return false;
  }

  const host = hostname.toLowerCase();
  const onApex = host === APEX_DOMAIN;
  const onHttp = protocol === 'http:';

  if (onApex || (onHttp && (host === CANONICAL_HOST || host.endsWith(APEX_DOMAIN)))) {
    window.location.replace(buildCanonicalHref(pathname, search, hash));
    return true;
  }

  return false;
}

export function normalizeProductionUrl(url) {
  if (!url || typeof url !== 'string') {
    return url;
  }
  if (url.startsWith('/') || isLocalHost(typeof window !== 'undefined' ? window.location.hostname : '')) {
    return url;
  }
  try {
    const parsed = new URL(url);
    if (isLocalHost(parsed.hostname)) {
      return url;
    }
    parsed.protocol = 'https:';
    if (parsed.hostname.toLowerCase() === APEX_DOMAIN) {
      parsed.hostname = CANONICAL_HOST;
    }
    return parsed.toString().replace(/\/$/, '');
  } catch {
    return url;
  }
}
