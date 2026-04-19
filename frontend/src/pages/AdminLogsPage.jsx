import { useEffect, useMemo, useState } from 'react';
import Navbar from '../components/Navbar';
import { useAuth } from '../contexts/AuthContext';
import { getSession } from '../lib/authClient';

const LOG_SOURCES = [
  { value: 'backend-error', label: 'Backend Errors' },
  { value: 'backend-out', label: 'Backend Output' },
  { value: 'database', label: 'Database Diagnostics' },
];

const formatError = (error) => {
  if (!error) return 'Unable to load logs.';
  return error.message || String(error);
};

export default function AdminLogsPage() {
  const { user } = useAuth();
  const [source, setSource] = useState('backend-error');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [refreshTick, setRefreshTick] = useState(0);

  useEffect(() => {
    let active = true;

    const loadLogs = async () => {
      setLoading(true);
      setError('');
      try {
        const session = await getSession();
        if (!session?.access_token) {
          throw new Error('Please log in again to view admin logs.');
        }
        const response = await fetch(`/api/admin/logs?source=${encodeURIComponent(source)}&lines=200`, {
          headers: {
            Authorization: `Bearer ${session.access_token}`,
          },
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(payload.error || 'Unable to load logs.');
        }
        if (active) {
          setData(payload.data);
        }
      } catch (fetchError) {
        if (active) {
          setData(null);
          setError(formatError(fetchError));
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };

    loadLogs();
    const timer = window.setInterval(() => {
      setRefreshTick((tick) => tick + 1);
    }, 15000);

    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [source, refreshTick]);

  const summaryItems = useMemo(() => {
    if (!data?.summary) return [];
    const tableCounts = data.summary.table_counts || {};
    const connectionStates = data.summary.connections || [];
    return [
      `Users: ${tableCounts.users ?? 0}`,
      `Interviews: ${tableCounts.interviews ?? 0}`,
      `Payments: ${tableCounts.payments ?? 0}`,
      `Questions: ${tableCounts.questions ?? 0}`,
      ...connectionStates.map((row) => `${row.state || 'unknown'}: ${row.total}`),
    ];
  }, [data]);

  return (
    <div className="min-h-screen bg-[#0b1020] text-white">
      <Navbar />
      <div className="mx-auto max-w-6xl px-4 py-8">
        <div className="mb-6 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.3em] text-blue-300/70">Admin Logs</p>
            <h1 className="mt-2 text-3xl font-semibold text-blue-200">Operational Viewer</h1>
            <p className="mt-2 max-w-3xl text-sm text-slate-300">
              Authenticated log access with backend-side admin checks, IP filtering, and sanitized output.
            </p>
            <p className="mt-2 text-xs text-slate-400">
              Signed in as: {user?.email || 'Unknown user'}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <select
              value={source}
              onChange={(event) => setSource(event.target.value)}
              className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white"
            >
              {LOG_SOURCES.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={() => setRefreshTick((tick) => tick + 1)}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500"
            >
              Refresh
            </button>
          </div>
        </div>

        {error && (
          <div className="mb-6 rounded-xl border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-100">
            {error}
          </div>
        )}

        <div className="grid gap-6 lg:grid-cols-[1.15fr_2fr]">
          <section className="rounded-2xl border border-slate-800 bg-slate-950/70 p-5 shadow-[0_20px_60px_rgba(0,0,0,0.35)]">
            <h2 className="text-lg font-semibold text-blue-100">Access Summary</h2>
            <div className="mt-4 space-y-2 text-sm text-slate-300">
              <div>Source: <span className="text-white">{data?.source || source}</span></div>
              <div>Client IP: <span className="text-white">{data?.client_ip || 'Pending'}</span></div>
              <div>Available: <span className="text-white">{data?.available === false ? 'No' : 'Yes'}</span></div>
              <div>Path: <span className="break-all text-white">{data?.path || 'Pending'}</span></div>
            </div>

            {summaryItems.length > 0 && (
              <div className="mt-6">
                <h3 className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-400">Database Snapshot</h3>
                <div className="mt-3 flex flex-wrap gap-2">
                  {summaryItems.map((item) => (
                    <span
                      key={item}
                      className="rounded-full border border-slate-700 bg-slate-900 px-3 py-1 text-xs text-slate-200"
                    >
                      {item}
                    </span>
                  ))}
                </div>
              </div>
            )}

            <div className="mt-6 rounded-xl border border-slate-800 bg-slate-900/80 p-4 text-xs text-slate-400">
              Output is sanitized before being returned. Secrets, bearer tokens, and emails are partially redacted.
            </div>
          </section>

          <section className="rounded-2xl border border-slate-800 bg-[#050814] p-5 shadow-[0_20px_60px_rgba(0,0,0,0.35)]">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-blue-100">Recent Lines</h2>
              <span className="text-xs text-slate-500">
                {loading ? 'Loading...' : `${data?.lines?.length || 0} lines`}
              </span>
            </div>

            <div className="max-h-[70vh] overflow-auto rounded-xl border border-slate-800 bg-black/40 p-4">
              <pre className="whitespace-pre-wrap break-words font-mono text-xs leading-6 text-slate-200">
                {loading ? 'Loading logs…' : (data?.lines?.join('\n') || 'No log lines available.')}
              </pre>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
