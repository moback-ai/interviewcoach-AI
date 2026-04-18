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
