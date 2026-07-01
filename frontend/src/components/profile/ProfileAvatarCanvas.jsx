import { useEffect, useRef } from 'react';
import { FETCH_CREDENTIALS, getAccessToken } from '../../lib/authClient';
import { getApiBaseUrl } from '../../utils/apiConfig';

const AVATAR_CANVAS_SIZE = 96;

function buildMyAvatarUrl() {
  const base = getApiBaseUrl().replace(/\/$/, '');
  if (base.endsWith('/api')) {
    return `${base}/functions/v1/me/avatar`;
  }
  return `${base}/me/avatar`;
}

async function fetchMyAvatarBlob() {
  const token = getAccessToken();
  const response = await fetch(buildMyAvatarUrl(), {
    ...FETCH_CREDENTIALS,
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!response.ok) {
    throw new Error(`Failed to load avatar (${response.status})`);
  }
  return response.blob();
}

function drawBitmapOnCanvas(canvas, bitmap) {
  const ctx = canvas.getContext('2d');
  if (!ctx) {
    return;
  }

  ctx.clearRect(0, 0, canvas.width, canvas.height);
  const scale = Math.max(canvas.width / bitmap.width, canvas.height / bitmap.height);
  const width = bitmap.width * scale;
  const height = bitmap.height * scale;
  const x = (canvas.width - width) / 2;
  const y = (canvas.height - height) / 2;
  ctx.drawImage(bitmap, x, y, width, height);
}

export default function ProfileAvatarCanvas({
  previewFile = null,
  loadSavedAvatar = false,
  reloadKey = 0,
  className = '',
}) {
  const canvasRef = useRef(null);

  useEffect(() => {
    let active = true;
    let bitmap = null;

    const render = async () => {
      const canvas = canvasRef.current;
      if (!canvas) {
        return;
      }

      const ctx = canvas.getContext('2d');
      if (!ctx) {
        return;
      }

      ctx.clearRect(0, 0, canvas.width, canvas.height);

      try {
        if (previewFile) {
          bitmap = await createImageBitmap(previewFile);
          if (!active) {
            bitmap.close();
            return;
          }
          drawBitmapOnCanvas(canvas, bitmap);
          bitmap.close();
          bitmap = null;
          return;
        }

        if (!loadSavedAvatar) {
          return;
        }

        const blob = await fetchMyAvatarBlob();
        if (!active) {
          return;
        }

        bitmap = await createImageBitmap(blob);
        if (!active) {
          bitmap.close();
          return;
        }

        drawBitmapOnCanvas(canvas, bitmap);
        bitmap.close();
        bitmap = null;
      } catch {
        if (active && ctx) {
          ctx.clearRect(0, 0, canvas.width, canvas.height);
        }
      }
    };

    render();

    return () => {
      active = false;
      if (bitmap) {
        bitmap.close();
      }
    };
  }, [previewFile, loadSavedAvatar, reloadKey]);

  return (
    <canvas
      ref={canvasRef}
      width={AVATAR_CANVAS_SIZE}
      height={AVATAR_CANVAS_SIZE}
      className={className}
      role="img"
      aria-label="Profile"
    />
  );
}
