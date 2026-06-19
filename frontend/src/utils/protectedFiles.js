import { getAccessToken } from '../lib/authClient';
import { getApiBaseUrl } from './apiConfig';

const FILES_PREFIX = '/api/files/';
const STORAGE_PREFIX = '/storage/';

function buildFileUrl(endpoint) {
  if (endpoint.startsWith('http://') || endpoint.startsWith('https://')) {
    return endpoint;
  }
  const normalizedBase = getApiBaseUrl().replace(/\/$/, '');
  const clean = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  if (clean.startsWith('/api/') && normalizedBase.endsWith('/api')) {
    return `${normalizedBase}${clean.slice(4)}`;
  }
  return `${normalizedBase}${clean}`;
}

export function isSafeImageSrc(url) {
  if (!url) return false;
  if (url.startsWith('blob:')) return true;
  if (url.startsWith('data:image/')) return true;
  try {
    const { protocol } = new URL(url, window.location.origin);
    return protocol === 'http:' || protocol === 'https:';
  } catch {
    return false;
  }
}

export function toProtectedFileUrl(urlOrPath) {
  if (!urlOrPath) return '';
  const value = String(urlOrPath).trim();
  if (!value) return '';

  if (value.includes(FILES_PREFIX)) {
    const idx = value.indexOf(FILES_PREFIX);
    return value.slice(idx);
  }

  if (value.includes(STORAGE_PREFIX)) {
    const idx = value.indexOf(STORAGE_PREFIX);
    const relative = value.slice(idx + STORAGE_PREFIX.length).replace(/^\/+/, '');
    return `${FILES_PREFIX}${relative}`;
  }

  if (value.startsWith('resumes/') || value.startsWith('audio/') || value.startsWith('avatars/')) {
    return `${FILES_PREFIX}${value.replace(/^\/+/, '')}`;
  }

  return value;
}

export function resolveAuthenticatedFileRequest(urlOrPath) {
  const protectedPath = toProtectedFileUrl(urlOrPath);
  if (!protectedPath) {
    throw new Error('Missing file URL');
  }

  if (protectedPath.startsWith('http://') || protectedPath.startsWith('https://')) {
    return protectedPath;
  }

  if (protectedPath.startsWith(FILES_PREFIX)) {
    return buildFileUrl(protectedPath);
  }

  return buildFileUrl(protectedPath.startsWith('/') ? protectedPath : `/${protectedPath}`);
}

export async function fetchAuthenticatedFile(urlOrPath, options = {}) {
  const requestUrl = resolveAuthenticatedFileRequest(urlOrPath);
  const token = getAccessToken();
  const headers = { ...(options.headers || {}) };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(requestUrl, {
    ...options,
    headers,
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch file (${response.status})`);
  }

  return response;
}

export async function fetchAuthenticatedBlob(urlOrPath, options = {}) {
  const response = await fetchAuthenticatedFile(urlOrPath, options);
  return response.blob();
}

export async function fetchAuthenticatedBlobUrl(urlOrPath, options = {}) {
  const blob = await fetchAuthenticatedBlob(urlOrPath, options);
  return URL.createObjectURL(blob);
}

export function revokeBlobUrl(blobUrl) {
  if (blobUrl && blobUrl.startsWith('blob:')) {
    URL.revokeObjectURL(blobUrl);
  }
}

export async function downloadAuthenticatedFile(urlOrPath, filename = 'download') {
  const blob = await fetchAuthenticatedBlob(urlOrPath);
  const blobUrl = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = blobUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  revokeBlobUrl(blobUrl);
}
