import { useEffect, useRef } from 'react';
import { FETCH_CREDENTIALS, getAccessToken } from '../lib/authClient';
import { getApiBaseUrl } from '../utils/apiConfig';
import { pauseInterviewTimer, tickInterviewTimer } from '../api';

const HEARTBEAT_MS = 45_000;

function pauseInterviewTimerKeepalive(interviewId) {
  if (!interviewId) {
    return;
  }

  const token = getAccessToken();
  const base = getApiBaseUrl().replace(/\/$/, '');
  fetch(`${base}/interviews/${interviewId}/timer-pause`, {
    method: 'POST',
    ...FETCH_CREDENTIALS,
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      'Content-Type': 'application/json',
    },
    body: '{}',
    keepalive: true,
  }).catch(() => {});
}

export function useInterviewTimer(interviewId, enabled) {
  const interviewIdRef = useRef(interviewId);
  interviewIdRef.current = interviewId;

  useEffect(() => {
    if (!enabled || !interviewId) {
      return undefined;
    }

    const tick = () => {
      if (document.visibilityState !== 'visible') {
        return;
      }
      tickInterviewTimer(interviewId).catch(() => {});
    };

    const pause = () => {
      pauseInterviewTimer(interviewId).catch(() => {});
    };

    tick();
    const intervalId = window.setInterval(tick, HEARTBEAT_MS);

    const onVisibilityChange = () => {
      if (document.visibilityState === 'hidden') {
        pause();
      } else {
        tick();
      }
    };

    document.addEventListener('visibilitychange', onVisibilityChange);

    return () => {
      window.clearInterval(intervalId);
      document.removeEventListener('visibilitychange', onVisibilityChange);
      pauseInterviewTimerKeepalive(interviewIdRef.current);
    };
  }, [enabled, interviewId]);
}
