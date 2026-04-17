const trimTrailingSlash = (value = '') => value.replace(/\/+$/, '');

export const getApiBaseUrl = () => {
  const configured = trimTrailingSlash(import.meta.env.VITE_API_BASE_URL || '');
  if (configured) {
    return configured;
  }

  if (typeof window !== 'undefined') {
    return `${window.location.origin}/api`;
  }

  return '/api';
};

export const getBackendOrigin = () => {
  const apiBaseUrl = getApiBaseUrl();
  return trimTrailingSlash(apiBaseUrl.replace(/\/api\/?$/, ''));
};

export const getStorageBaseUrl = () => {
  const configured = trimTrailingSlash(import.meta.env.VITE_STORAGE_URL || '');
  if (configured) {
    return configured;
  }

  return `${getBackendOrigin()}/storage`;
};
