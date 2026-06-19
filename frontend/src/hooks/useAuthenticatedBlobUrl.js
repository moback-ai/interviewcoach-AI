import { useEffect, useState } from 'react';
import {
  fetchAuthenticatedBlobUrl,
  revokeBlobUrl,
  toProtectedFileUrl,
} from '../utils/protectedFiles';

function needsAuthenticatedFetch(url) {
  if (!url) return false;
  if (url.startsWith('blob:') || url.startsWith('data:')) return false;
  return toProtectedFileUrl(url).includes('/api/files/');
}

export function useAuthenticatedBlobUrl(sourceUrl) {
  const [blobUrl, setBlobUrl] = useState('');

  useEffect(() => {
    let active = true;
    let created = '';

    const load = async () => {
      if (!sourceUrl) {
        if (active) setBlobUrl('');
        return;
      }

      if (!needsAuthenticatedFetch(sourceUrl)) {
        if (active) setBlobUrl('');
        return;
      }

      try {
        created = await fetchAuthenticatedBlobUrl(sourceUrl);
        if (active) setBlobUrl(created);
      } catch {
        if (active) setBlobUrl('');
      }
    };

    load();

    return () => {
      active = false;
      revokeBlobUrl(created);
    };
  }, [sourceUrl]);

  return blobUrl;
}

export async function createAuthenticatedAudioElement(audioUrl) {
  if (!audioUrl) {
    throw new Error('Missing audio URL');
  }

  if (audioUrl.startsWith('blob:')) {
    return { audio: new Audio(audioUrl), blobUrl: null };
  }

  if (!needsAuthenticatedFetch(audioUrl)) {
    throw new Error('Unsupported audio URL');
  }

  const blobUrl = await fetchAuthenticatedBlobUrl(audioUrl);
  return { audio: new Audio(blobUrl), blobUrl };
}
