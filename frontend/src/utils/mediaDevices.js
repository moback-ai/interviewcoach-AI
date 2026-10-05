const isLocalhostHost = (hostname = '') =>
  hostname === 'localhost' ||
  hostname === '127.0.0.1' ||
  hostname === '::1';

export const isMediaCaptureSupported = () => {
  if (typeof navigator === 'undefined') {
    return false;
  }

  if (navigator.mediaDevices?.getUserMedia) {
    return true;
  }

  return Boolean(
    navigator.getUserMedia ||
    navigator.webkitGetUserMedia ||
    navigator.mozGetUserMedia ||
    navigator.msGetUserMedia
  );
};

export const getMediaAccessErrorMessage = (kind = 'camera') => {
  const hostname = typeof window !== 'undefined' ? window.location.hostname : '';
  const isLocalhost = isLocalhostHost(hostname);

  if (typeof window !== 'undefined' && !window.isSecureContext && !isLocalhost) {
    return `${kind === 'audio' ? 'Microphone' : 'Camera'} access requires HTTPS on this site. Open the app over HTTPS (or localhost) and try again.`;
  }

  return `${kind === 'audio' ? 'Microphone' : 'Camera'} access is not supported in this browser. Try the latest Chrome, Edge, or Safari.`;
};

export const getInterviewCameraConstraints = (headTrackingEnabled) => ({
  video: headTrackingEnabled
    ? {
        width: { ideal: 1920 },
        height: { ideal: 1080 },
        frameRate: { ideal: 30 },
        facingMode: 'user',
      }
    : {
        width: { ideal: 1280 },
        height: { ideal: 720 },
        frameRate: { ideal: 15, max: 24 },
        facingMode: 'user',
      },
  audio: false,
});

export const applyInterviewCameraConstraints = async (stream, headTrackingEnabled) => {
  const track = stream?.getVideoTracks?.()[0];
  if (!track) {
    return false;
  }

  try {
    await track.applyConstraints(getInterviewCameraConstraints(headTrackingEnabled).video);
  } catch {
    return false;
  }

  const { width = 0, height = 0 } = track.getSettings?.() || {};
  if (width <= 0 || height <= 0) {
    return false;
  }

  if (headTrackingEnabled) {
    return width >= 960 && height >= 540;
  }

  return width <= 1440;
};

export const requestUserMedia = async (constraints) => {
  if (typeof navigator === 'undefined') {
    const error = new Error('Media devices are unavailable.');
    error.name = 'MediaDevicesUnavailable';
    throw error;
  }

  if (navigator.mediaDevices?.getUserMedia) {
    return navigator.mediaDevices.getUserMedia(constraints);
  }

  const legacyGetUserMedia =
    navigator.getUserMedia ||
    navigator.webkitGetUserMedia ||
    navigator.mozGetUserMedia ||
    navigator.msGetUserMedia;

  if (!legacyGetUserMedia) {
    const error = new Error(getMediaAccessErrorMessage(constraints.audio ? 'audio' : 'camera'));
    error.name = 'MediaDevicesUnsupported';
    throw error;
  }

  return new Promise((resolve, reject) => {
    legacyGetUserMedia.call(navigator, constraints, resolve, reject);
  });
};
