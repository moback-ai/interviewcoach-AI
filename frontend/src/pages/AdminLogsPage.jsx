import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import Navbar from '../components/Navbar';
import PageWavesShell from '../components/common/PageWavesShell';
import { useAuth } from '../contexts/AuthContext';
import { getSession } from '../lib/authClient';

const LOG_SOURCES = [
  { value: 'deployment-live', label: 'Deployment Live Log' },
  { value: 'backend-error', label: 'Backend Errors' },
  { value: 'backend-out', label: 'Backend Output' },
  { value: 'frontend-access', label: 'Frontend (nginx)' },
  { value: 'database', label: 'Database Diagnostics' },
  { value: 'ai-diagnostics', label: 'AI Diagnostics' },
];

const LIVE_STREAM_SOURCES = new Set(['deployment-live', 'backend-error', 'backend-out', 'frontend-access']);
const MAX_LIVE_LINES = 400;

const formatError = (error) => {
  if (!error) return 'Unable to load logs.';
  return error.message || String(error);
};

const clampLiveLines = (lines) => lines.slice(-MAX_LIVE_LINES);

const parseJsonSafely = (value) => {
  try {
    return JSON.parse(value);
  } catch {
    return null;
  }
};

const METRICS_REFRESH_MS = 20000;

const formatBytes = (bytes) => {
  if (!bytes && bytes !== 0) return '—';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let value = bytes;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  return `${value.toFixed(value >= 10 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
};

const formatUptime = (seconds) => {
  if (!seconds && seconds !== 0) return '—';
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${mins}m`;
  return `${mins}m`;
};

const usageTone = (percent) => {
  if (percent == null) return 'text-slate-400';
  if (percent >= 90) return 'text-red-300';
  if (percent >= 75) return 'text-amber-300';
  return 'text-emerald-300';
};

const usageBarTone = (percent) => {
  if (percent == null) return 'bg-slate-600';
  if (percent >= 90) return 'bg-red-500';
  if (percent >= 75) return 'bg-amber-500';
  return 'bg-emerald-500';
};

function MetricBar({ label, percent }) {
  const safePercent = percent == null ? 0 : Math.max(0, Math.min(100, percent));
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs text-slate-400">
        <span>{label}</span>
        <span className={usageTone(percent)}>{percent == null ? '—' : `${percent}%`}</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-slate-800">
        <div
          className={`h-full rounded-full transition-all ${usageBarTone(percent)}`}
          style={{ width: `${safePercent}%` }}
        />
      </div>
    </div>
  );
}

function ServerMetricsCard({ host }) {
  const role = host?.role || 'Unknown';
  const titleMap = {
    BACKEND: 'API (Backend)',
    FRONTEND: 'Frontend',
    AI: 'AI / Ollama',
    DB: 'Database (RDS)',
  };

  if (!host?.available) {
    return (
      <div className="rounded-2xl border border-slate-800 bg-slate-950/80 p-4">
        <div className="text-sm font-semibold text-blue-100">{titleMap[role] || role}</div>
        <div className="mt-1 text-xs text-slate-500">{host?.host || 'unavailable'}</div>
        <p className="mt-3 text-sm text-amber-200">{host?.error || 'Metrics unavailable'}</p>
      </div>
    );
  }

  if (role === 'DB') {
    return (
      <div className="rounded-2xl border border-slate-800 bg-slate-950/80 p-4">
        <div className="text-sm font-semibold text-blue-100">{titleMap.DB}</div>
        <div className="mt-1 text-xs text-slate-500">{host.host}</div>
        <div className="mt-4 space-y-2 text-sm text-slate-300">
          <div>Connections: <span className="text-white">{host.connection_total ?? '—'}</span></div>
          <div>DB size: <span className="text-white">{formatBytes(host.database_size_bytes)}</span></div>
          {(host.connections || []).map((row) => (
            <div key={row.state} className="text-xs text-slate-400">
              {row.state}: {row.total}
            </div>
          ))}
        </div>
        <p className="mt-3 text-[11px] text-slate-500">{host.note}</p>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-950/80 p-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="text-sm font-semibold text-blue-100">{titleMap[role] || role}</div>
          <div className="mt-1 text-xs text-slate-500">{host.host}</div>
        </div>
        <div className="text-right text-[11px] text-slate-500">
          <div>{host.cpu_cores} cores</div>
          <div>up {formatUptime(host.uptime_seconds)}</div>
        </div>
      </div>
      <div className="mt-4 space-y-3">
        <MetricBar label="CPU" percent={host.cpu_percent} />
        <MetricBar label="RAM" percent={host.memory_percent} />
        <MetricBar label="Disk" percent={host.disk_percent} />
      </div>
      <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-slate-500">
        <span>Load {host.load_1 ?? '—'}</span>
        <span>RAM {formatBytes(host.memory_used_bytes)} / {formatBytes(host.memory_total_bytes)}</span>
        <span>Disk {formatBytes(host.disk_free_bytes)} free</span>
      </div>
    </div>
  );
}

export default function AdminLogsPage() {
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const activeView = searchParams.get('view') || 'live';
  const source = searchParams.get('source') || 'deployment-live';

  const [data, setData] = useState(null);
  const [filesData, setFilesData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filesLoading, setFilesLoading] = useState(true);
  const [error, setError] = useState('');
  const [filesError, setFilesError] = useState('');
  const [refreshTick, setRefreshTick] = useState(0);
  const [streamStatus, setStreamStatus] = useState('idle');
  const [liveLines, setLiveLines] = useState([]);
  const [downloadingPath, setDownloadingPath] = useState('');
  const [metricsData, setMetricsData] = useState(null);
  const [metricsLoading, setMetricsLoading] = useState(true);
  const [metricsError, setMetricsError] = useState('');

  useEffect(() => {
    let active = true;
    let intervalId;

    const loadMetrics = async () => {
      try {
        const session = await getSession();
        if (!session?.access_token) {
          throw new Error('Please log in again to view server metrics.');
        }

        const response = await fetch('/api/admin/metrics', {
          headers: {
            Authorization: `Bearer ${session.access_token}`,
          },
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(payload.error || 'Unable to load server metrics.');
        }

        if (active) {
          setMetricsData(payload.data);
          setMetricsError('');
        }
      } catch (fetchError) {
        if (active) {
          setMetricsData(null);
          setMetricsError(formatError(fetchError));
        }
      } finally {
        if (active) {
          setMetricsLoading(false);
        }
      }
    };

    loadMetrics();
    intervalId = window.setInterval(loadMetrics, METRICS_REFRESH_MS);

    return () => {
      active = false;
      window.clearInterval(intervalId);
    };
  }, [refreshTick]);

  useEffect(() => {
    let active = true;

    const loadSnapshot = async () => {
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
          setLiveLines(clampLiveLines(payload.data?.lines || []));
        }
      } catch (fetchError) {
        if (active) {
          setData(null);
          setLiveLines([]);
          setError(formatError(fetchError));
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };

    loadSnapshot();
    return () => {
      active = false;
    };
  }, [source, refreshTick]);

  useEffect(() => {
    let active = true;

    const loadFiles = async () => {
      setFilesLoading(true);
      setFilesError('');
      try {
        const session = await getSession();
        if (!session?.access_token) {
          throw new Error('Please log in again to view archived logs.');
        }

        const response = await fetch('/api/admin/logs/files', {
          headers: {
            Authorization: `Bearer ${session.access_token}`,
          },
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(payload.error || 'Unable to load archived logs.');
        }

        if (active) {
          setFilesData(payload.data?.files || []);
        }
      } catch (fetchError) {
        if (active) {
          setFilesData([]);
          setFilesError(formatError(fetchError));
        }
      } finally {
        if (active) {
          setFilesLoading(false);
        }
      }
    };

    loadFiles();
    return () => {
      active = false;
    };
  }, [refreshTick]);

  useEffect(() => {
    if (activeView !== 'live' || !LIVE_STREAM_SOURCES.has(source)) {
      setStreamStatus('idle');
      return undefined;
    }

    const controller = new AbortController();
    let mounted = true;

    const streamLogs = async () => {
      setStreamStatus('connecting');
      try {
        const session = await getSession();
        if (!session?.access_token) {
          throw new Error('Please log in again to stream admin logs.');
        }

        const response = await fetch(`/api/admin/logs/stream?source=${encodeURIComponent(source)}`, {
          headers: {
            Authorization: `Bearer ${session.access_token}`,
          },
          signal: controller.signal,
        });

        if (!response.ok || !response.body) {
          const payload = await response.json().catch(() => ({}));
          throw new Error(payload.error || 'Unable to open the live log stream.');
        }

        if (mounted) {
          setStreamStatus('live');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (mounted) {
          const { done, value } = await reader.read();
          if (done) {
            break;
          }

          buffer += decoder.decode(value, { stream: true });
          const parts = buffer.split('\n');
          buffer = parts.pop() || '';

          for (const part of parts) {
            const parsed = parseJsonSafely(part.trim());
            if (!parsed || parsed.type !== 'line' || !parsed.line) {
              continue;
            }

            setLiveLines((current) => clampLiveLines([...current, parsed.line]));
          }
        }

        if (mounted) {
          setStreamStatus('idle');
        }
      } catch (streamError) {
        if (mounted && streamError.name !== 'AbortError') {
          setStreamStatus('error');
          setError(formatError(streamError));
        }
      }
    };

    streamLogs();

    return () => {
      mounted = false;
      controller.abort();
    };
  }, [activeView, source, refreshTick]);

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

  const visibleLines = activeView === 'live' && LIVE_STREAM_SOURCES.has(source)
    ? liveLines
    : (data?.lines || []);

  const handleViewChange = (nextView) => {
    const next = new URLSearchParams(searchParams);
    next.set('view', nextView);
    next.set('source', source);
    setSearchParams(next, { replace: true });
  };

  const handleSourceChange = (nextSource) => {
    const next = new URLSearchParams(searchParams);
    next.set('source', nextSource);
    if (!next.get('view')) {
      next.set('view', 'live');
    }
    setSearchParams(next, { replace: true });
  };

  const handleDownload = async (file) => {
    setDownloadingPath(file.relative_path);
    try {
      const session = await getSession();
      if (!session?.access_token) {
        throw new Error('Please log in again to download logs.');
      }

      const response = await fetch(file.download_url, {
        headers: {
          Authorization: `Bearer ${session.access_token}`,
        },
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.error || 'Unable to download the selected log file.');
      }

      const blob = await response.blob();
      const blobUrl = window.URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = blobUrl;
      anchor.download = file.name;
      anchor.click();
      window.URL.revokeObjectURL(blobUrl);
    } catch (downloadError) {
      setFilesError(formatError(downloadError));
    } finally {
      setDownloadingPath('');
    }
  };

  return (
    <>
      <Navbar />
      <PageWavesShell contentClassName="text-white px-4 py-8">
        <div className="mx-auto max-w-7xl w-full">
        <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.3em] text-blue-300/70">Admin Logs</p>
            <h1 className="mt-2 text-3xl font-semibold text-blue-200">Deployment and Runtime Logs</h1>
            <p className="mt-2 max-w-3xl text-sm text-slate-300">
              Live deployment tails, backend runtime output, and archived log files are available here with admin auth and server-side redaction.
            </p>
            <p className="mt-2 text-xs text-slate-400">
              Signed in as: {user?.email || 'Unknown user'}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <div className="inline-flex rounded-xl border border-slate-700 bg-slate-900/80 p-1">
              <button
                type="button"
                onClick={() => handleViewChange('live')}
                className={`rounded-lg px-4 py-2 text-sm ${activeView === 'live' ? 'bg-blue-600 text-white' : 'text-slate-300'}`}
              >
                Live View
              </button>
              <button
                type="button"
                onClick={() => handleViewChange('files')}
                className={`rounded-lg px-4 py-2 text-sm ${activeView === 'files' ? 'bg-blue-600 text-white' : 'text-slate-300'}`}
              >
                Folder View
              </button>
            </div>

            <select
              value={source}
              onChange={(event) => handleSourceChange(event.target.value)}
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

        {filesError && (
          <div className="mb-6 rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
            {filesError}
          </div>
        )}

        <section className="mb-6 rounded-2xl border border-slate-800 bg-slate-950/70 p-5 shadow-[0_20px_60px_rgba(0,0,0,0.35)]">
          <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-blue-100">Server Metrics</h2>
              <p className="text-xs text-slate-400">
                CPU, RAM, and disk per host. Auto-refreshes every {METRICS_REFRESH_MS / 1000}s.
                {metricsData?.collected_at ? ` Last sample: ${metricsData.collected_at}` : ''}
              </p>
            </div>
            <span className="text-xs uppercase tracking-[0.2em] text-slate-500">
              {metricsLoading ? 'Loading…' : 'Live'}
            </span>
          </div>

          {metricsError && (
            <div className="mb-4 rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
              {metricsError}
            </div>
          )}

          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {(metricsData?.hosts || []).map((host) => (
              <ServerMetricsCard key={host.role} host={host} />
            ))}
            {!metricsLoading && !(metricsData?.hosts || []).length && (
              <div className="col-span-full rounded-xl border border-slate-800 bg-slate-900/70 px-4 py-3 text-sm text-slate-300">
                No metrics available yet.
              </div>
            )}
          </div>
        </section>

        <div className="grid gap-6 xl:grid-cols-[1.05fr_1.55fr_1.2fr]">
          <section className="rounded-2xl border border-slate-800 bg-slate-950/70 p-5 shadow-[0_20px_60px_rgba(0,0,0,0.35)]">
            <h2 className="text-lg font-semibold text-blue-100">Access Summary</h2>
            <div className="mt-4 space-y-2 text-sm text-slate-300">
              <div>Source: <span className="text-white">{data?.source || source}</span></div>
              <div>Client IP: <span className="text-white">{data?.client_ip || 'Pending'}</span></div>
              <div>Available: <span className="text-white">{data?.available === false ? 'No' : 'Yes'}</span></div>
              <div>Path: <span className="break-all text-white">{data?.path || 'Pending'}</span></div>
              <div>
                Stream status:
                <span className="ml-2 text-white">
                  {activeView === 'live' && LIVE_STREAM_SOURCES.has(source) ? streamStatus : 'snapshot'}
                </span>
              </div>
            </div>

            <div className="mt-6 space-y-3 text-sm text-slate-300">
              <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-3">
                <div className="text-xs uppercase tracking-[0.2em] text-slate-500">Live Logs URL</div>
                <a href={data?.live_url || '/admin/logs?view=live'} className="mt-2 block break-all text-blue-300 hover:text-blue-200">
                  {data?.live_url || `${window.location.origin}/admin/logs?view=live&source=${source}`}
                </a>
              </div>
              <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-3">
                <div className="text-xs uppercase tracking-[0.2em] text-slate-500">Folder URL</div>
                <a href={data?.folder_url || '/admin/logs?view=files'} className="mt-2 block break-all text-blue-300 hover:text-blue-200">
                  {data?.folder_url || `${window.location.origin}/admin/logs?view=files`}
                </a>
              </div>
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
              Secrets, bearer tokens, and emails are redacted before content is returned to the browser.
            </div>
          </section>

          <section className="rounded-2xl border border-slate-800 bg-[#050814] p-5 shadow-[0_20px_60px_rgba(0,0,0,0.35)]">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-blue-100">
                {activeView === 'live' ? 'Live Tail' : 'Snapshot'}
              </h2>
              <span className="text-xs text-slate-500">
                {loading ? 'Loading...' : `${visibleLines.length} lines`}
              </span>
            </div>

            <div className="mb-4 flex items-center justify-between rounded-xl border border-slate-800 bg-slate-900/60 px-4 py-3 text-xs text-slate-400">
              <span>
                {activeView === 'live' && LIVE_STREAM_SOURCES.has(source)
                  ? 'Real-time stream is connected to the selected source.'
                  : 'Showing the latest sanitized snapshot for the selected source.'}
              </span>
              <span className="uppercase tracking-[0.2em] text-blue-300/80">
                {activeView === 'live' && LIVE_STREAM_SOURCES.has(source) ? streamStatus : 'snapshot'}
              </span>
            </div>

            <div className="max-h-[70vh] overflow-auto rounded-xl border border-slate-800 bg-black/40 p-4">
              <pre className="whitespace-pre-wrap break-words font-mono text-xs leading-6 text-slate-200">
                {loading ? 'Loading logs…' : (visibleLines.join('\n') || 'No log lines available.')}
              </pre>
            </div>
          </section>

          <section className="rounded-2xl border border-slate-800 bg-slate-950/70 p-5 shadow-[0_20px_60px_rgba(0,0,0,0.35)]">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-blue-100">Folder View</h2>
              <span className="text-xs text-slate-500">
                {filesLoading ? 'Loading...' : `${filesData.length} files`}
              </span>
            </div>

            <div className="mb-4 rounded-xl border border-slate-800 bg-slate-900/60 px-4 py-3 text-xs text-slate-400">
              Archived zip bundles are kept here after cleanup, while recent live logs stay available for debugging.
            </div>

            <div className="max-h-[70vh] space-y-3 overflow-auto">
              {filesLoading && (
                <div className="rounded-xl border border-slate-800 bg-slate-900/70 px-4 py-3 text-sm text-slate-300">
                  Loading log folder…
                </div>
              )}

              {!filesLoading && filesData.length === 0 && (
                <div className="rounded-xl border border-slate-800 bg-slate-900/70 px-4 py-3 text-sm text-slate-300">
                  No archived or managed log files are available yet.
                </div>
              )}

              {filesData.map((file) => (
                <div key={file.relative_path} className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium text-white">{file.name}</div>
                      <div className="mt-1 break-all text-xs text-slate-400">{file.relative_path}</div>
                      <div className="mt-2 flex flex-wrap gap-2 text-[11px] uppercase tracking-[0.18em] text-slate-500">
                        <span>{file.category}</span>
                        <span>{Math.max(file.size_bytes / 1024, 1).toFixed(1)} KB</span>
                        <span>{file.modified_at}</span>
                      </div>
                    </div>

                    <button
                      type="button"
                      onClick={() => handleDownload(file)}
                      className="rounded-lg bg-slate-800 px-3 py-2 text-xs font-medium text-white hover:bg-slate-700"
                    >
                      {downloadingPath === file.relative_path ? 'Downloading…' : 'Download'}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </section>
        </div>
        </div>
      </PageWavesShell>
    </>
  );
}
