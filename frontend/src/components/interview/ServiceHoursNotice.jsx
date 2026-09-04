import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { FiClock } from 'react-icons/fi';
import { apiGet } from '../../api';

const MAX_CHECK_INTERVAL_MS = 12 * 60 * 60 * 1000; // 12 hours max cap
const MIN_CHECK_INTERVAL_MS = 10 * 1000; // 10 seconds min floor

const FALLBACK_STATUS = {
  is_open: false,
  title: 'Under maintenance',
  start: '10:00',
  end: '19:00',
  timezone: 'Asia/Kolkata',
  message:
    'InterviewCoach is under maintenance from 7:00 PM until 10:00 AM IST. We are live daily from 10:00 AM to 7:00 PM — stay tuned and check back when we open.',
};

let inFlightFetch = null;

async function fetchServiceHoursDeduplicated() {
  if (inFlightFetch) {
    return inFlightFetch;
  }
  inFlightFetch = apiGet('/api/service-hours').finally(() => {
    inFlightFetch = null;
  });
  return inFlightFetch;
}

function getMsUntilNextTransition(status) {
  if (!status) {
    return MAX_CHECK_INTERVAL_MS;
  }

  if (typeof status.seconds_until_next_transition === 'number') {
    const diffMs = (status.seconds_until_next_transition * 1000) + 2000;
    return Math.min(Math.max(diffMs, MIN_CHECK_INTERVAL_MS), MAX_CHECK_INTERVAL_MS);
  }

  if (!status.start || !status.end) {
    return MAX_CHECK_INTERVAL_MS;
  }

  try {
    const targetHHMM = status.is_open ? status.end : status.start;
    const [targetH, targetM] = targetHHMM.split(':').map(Number);
    const tz = status.timezone || 'Asia/Kolkata';

    const now = new Date();
    const formatter = new Intl.DateTimeFormat('en-US', {
      timeZone: tz,
      hour: 'numeric',
      minute: 'numeric',
      second: 'numeric',
      hour12: false,
    });

    const parts = formatter.formatToParts(now);
    const p = {};
    parts.forEach(({ type, value }) => {
      p[type] = value;
    });

    const currentH = Number(p.hour) % 24;
    const currentM = Number(p.minute);
    const currentS = Number(p.second);

    const currentTotalSec = currentH * 3600 + currentM * 60 + currentS;
    let targetTotalSec = targetH * 3600 + targetM * 60;

    if (targetTotalSec <= currentTotalSec) {
      targetTotalSec += 24 * 3600;
    }

    const diffMs = (targetTotalSec - currentTotalSec) * 1000 + 2000;
    return Math.min(Math.max(diffMs, MIN_CHECK_INTERVAL_MS), MAX_CHECK_INTERVAL_MS);
  } catch {
    return MAX_CHECK_INTERVAL_MS;
  }
}

export default function ServiceHoursNotice() {
  const [status, setStatus] = useState(null);

  useEffect(() => {
    let cancelled = false;
    let timerId = null;
    let isFetching = false;

    const clearTimer = () => {
      if (timerId) {
        window.clearTimeout(timerId);
        timerId = null;
      }
    };

    const loadStatus = async () => {
      if (isFetching) return;
      isFetching = true;
      clearTimer();

      let currentData = null;
      try {
        const res = await fetchServiceHoursDeduplicated();
        if (!cancelled && res?.data) {
          currentData = res.data;
          setStatus(res.data);
        }
      } catch {
        if (!cancelled) {
          currentData = FALLBACK_STATUS;
          setStatus(FALLBACK_STATUS);
        }
      } finally {
        isFetching = false;
      }

      if (!cancelled && document.visibilityState === 'visible') {
        clearTimer();
        const delay = getMsUntilNextTransition(currentData);
        timerId = window.setTimeout(loadStatus, delay);
      }
    };

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        loadStatus();
      } else {
        clearTimer();
      }
    };

    loadStatus();
    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      cancelled = true;
      clearTimer();
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, []);

  if (!status || status.is_open) {
    return null;
  }

  const title = status.title || 'Under maintenance';
  const message = status.message
    || `InterviewCoach is available ${status.start}–${status.end} (${status.timezone}). Please check back during service hours.`;

  return (
    <div
      className="service-hours-banner"
      role="status"
      aria-live="polite"
    >
      <div className="service-hours-banner__inner">
        <FiClock className="service-hours-banner__icon" aria-hidden="true" />
        <div className="service-hours-banner__copy">
          <p className="service-hours-banner__title">{title}</p>
          <p className="service-hours-banner__message">{message}</p>
        </div>
        <Link to="/faq#contact" className="service-hours-banner__link">
          Reach out
        </Link>
      </div>
    </div>
  );
}
