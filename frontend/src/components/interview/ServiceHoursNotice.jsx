import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { FiClock } from 'react-icons/fi';
import { apiGet } from '../../api';

const POLL_MS = 60_000;

const FALLBACK_STATUS = {
  is_open: false,
  title: 'Under maintenance',
  start: '10:00',
  end: '19:00',
  timezone: 'Asia/Kolkata',
  message:
    'InterviewCoach is under maintenance from 7:00 PM until 10:00 AM IST. We are live daily from 10:00 AM to 7:00 PM — stay tuned and check back when we open.',
};

export default function ServiceHoursNotice() {
  const [status, setStatus] = useState(null);

  useEffect(() => {
    let cancelled = false;

    const loadStatus = async () => {
      try {
        const res = await apiGet('/api/service-hours');
        if (!cancelled && res?.data) {
          setStatus(res.data);
        }
      } catch {
        if (!cancelled) {
          setStatus(FALLBACK_STATUS);
        }
      }
    };

    loadStatus();
    const timer = window.setInterval(loadStatus, POLL_MS);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
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
