import { useEffect, useState } from 'react';
import { apiGet } from '../../api';

export default function ServiceHoursNotice() {
  const [status, setStatus] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await apiGet('/api/service-hours');
        if (!cancelled && res?.data) {
          setStatus(res.data);
        }
      } catch {
        if (!cancelled) {
          setStatus({
            is_open: false,
            start: '10:00',
            end: '19:00',
            timezone: 'Asia/Kolkata',
            message: 'InterviewCoach is available 10:00 AM – 7:00 PM IST.',
          });
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (!status || status.is_open) {
    return null;
  }

  return (
    <div
      className="mx-4 mt-4 rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-100"
      role="status"
    >
      <p className="font-medium">Outside service hours</p>
      <p className="mt-1 opacity-90">
        {status.message || `Available ${status.start}–${status.end} (${status.timezone}).`}
      </p>
    </div>
  );
}
