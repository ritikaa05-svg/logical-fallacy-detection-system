import { useState, useEffect, useMemo, useRef } from 'react';
import type { SystemHealth } from '../types/api';

interface FlatEntry {
  label: string;
  value: string;
  key: string;
}

function flatten(obj: Record<string, unknown>, prefix = ''): FlatEntry[] {
  const entries: FlatEntry[] = [];
  for (const [key, val] of Object.entries(obj)) {
    const label = prefix ? `${prefix} > ${key}` : key;
    if (val !== null && typeof val === 'object' && !Array.isArray(val)) {
      entries.push(...flatten(val as Record<string, unknown>, label));
    } else {
      entries.push({
        key: label,
        label: label.replace(/_/g, ' '),
        value: val == null ? '—' : Array.isArray(val) ? val.join(', ') : String(val),
      });
    }
  }
  return entries;
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between px-4 sm:px-5 py-2.5 border-b border-app-border last:border-0 hover:bg-app-card-alt transition-colors">
      <span className="text-sm text-app-text-secondary">{label}</span>
      <span className="text-sm font-mono text-app-text truncate ml-4 max-w-[60%] text-right">{value}</span>
    </div>
  );
}

export default function Status() {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    let cancelled = false;
    const fetchHealth = async () => {
      try {
        const res = await fetch('/api/v1/health');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json: SystemHealth = await res.json();
        if (!cancelled && mountedRef.current) {
          setHealth(json);
          setError(null);
        }
      } catch (err: unknown) {
        if (!cancelled && mountedRef.current) {
          const msg = err instanceof Error ? err.message : 'Failed to load';
          setHealth(prev => {
            if (!prev) setError(msg);
            return prev;
          });
        }
      } finally {
        if (!cancelled && mountedRef.current) setLoading(false);
      }
    };
    fetchHealth();
    const interval = setInterval(fetchHealth, 15_000);
    return () => { cancelled = true; clearInterval(interval); mountedRef.current = false; };
  }, [health]);

  const sections = useMemo(() => {
    if (!health) return [];
    return [
      {
        title: 'Overview',
        entries: flatten({
          status: health.status,
          version: health.version,
          classifier_mode: health.classifier_mode,
          last_updated: health.timestamp,
        }),
      },
      ...(health.device && typeof health.device === 'object'
        ? [{ title: 'Device', entries: flatten(health.device as Record<string, unknown>) }]
        : []),
      ...(health.cache && typeof health.cache === 'object'
        ? [{ title: 'Cache', entries: flatten(health.cache as Record<string, unknown>) }]
        : []),
    ];
  }, [health]);

  if (loading) {
    return (
      <main className="min-h-screen bg-app-bg">
        <header className="bg-app-card border-b border-app-border px-4 sm:px-6 py-3">
          <div className="max-w-4xl mx-auto"><h1 className="text-sm font-bold text-app-text uppercase tracking-wider">System Status</h1></div>
        </header>
        <div className="max-w-4xl mx-auto p-4 sm:p-6 space-y-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="bg-app-card border border-app-border rounded-xl p-5 animate-pulse">
              <div className="h-4 bg-app-card-alt rounded w-24 mb-4" />
              <div className="space-y-2">
                {[1, 2, 3].map(j => <div key={j} className="h-3 bg-app-card-alt rounded w-full" />)}
              </div>
            </div>
          ))}
        </div>
      </main>
    );
  }

  if (!health) {
    return (
      <main className="min-h-screen bg-app-bg">
        <header className="bg-app-card border-b border-app-border px-4 sm:px-6 py-3">
          <div className="max-w-4xl mx-auto"><h1 className="text-sm font-bold text-app-text uppercase tracking-wider">System Status</h1></div>
        </header>
        <div className="max-w-4xl mx-auto p-4 sm:p-6">
          <div className="bg-[var(--badge-red-bg)] border border-[var(--badge-red-border)] text-[var(--badge-red-text)] rounded-xl p-4 text-sm font-mono">
            {error || 'Unable to fetch system status.'}
          </div>
        </div>
      </main>
    );
  }

  const isHealthy = health.status === 'healthy';

  const staleData = error && health;

  return (
    <main className="min-h-screen bg-app-bg">
      <header className="bg-app-card border-b border-app-border px-4 sm:px-6 py-3">
        <div className="max-w-4xl mx-auto">
          <h1 className="text-sm font-bold text-app-text uppercase tracking-wider">System Status</h1>
        </div>
      </header>

      {staleData && (
        <div className="max-w-4xl mx-auto mt-4 px-4 sm:px-6" aria-live="polite">
          <div className="bg-[var(--badge-amber-bg)] border border-[var(--badge-amber-border)] text-[var(--badge-amber-text)] rounded-xl px-4 py-2.5 text-xs font-semibold flex items-center gap-2">
            <span>&#9888;&#65039;</span>
            Showing cached data — refresh failed. Last successful update: {new Date(health.timestamp).toLocaleTimeString()}
          </div>
        </div>
      )}

      <div className="max-w-4xl mx-auto p-4 sm:p-6 space-y-5">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {[
            {
              label: 'Status',
              value: isHealthy ? 'Healthy' : 'Degraded',
              color: isHealthy ? 'text-[var(--badge-healthy-text)]' : 'text-[var(--badge-unhealthy-text)]',
              border: isHealthy ? 'border-[var(--badge-healthy-border)]' : 'border-[var(--badge-unhealthy-border)]',
              bg: isHealthy ? 'bg-[var(--badge-healthy-bg)]' : 'bg-[var(--badge-unhealthy-bg)]',
            },
            {
              label: 'Classifier',
              value: health.classifier_mode,
              color: health.classifier_mode === 'Mock' ? 'text-[var(--badge-mock-text)]' : 'text-[var(--badge-healthy-text)]',
              border: health.classifier_mode === 'Mock' ? 'border-[var(--badge-mock-border)]' : 'border-[var(--badge-healthy-border)]',
              bg: health.classifier_mode === 'Mock' ? 'bg-[var(--badge-mock-bg)]' : 'bg-[var(--badge-healthy-bg)]',
            },
            {
              label: 'Last Updated',
              value: new Date(health.timestamp).toLocaleTimeString(),
              color: 'text-app-text-secondary',
              border: 'border-app-border',
              bg: 'bg-app-card',
            },
          ].map(s => (
            <div key={s.label} className={`rounded-xl border ${s.border} ${s.bg} p-4 transition-colors hover:border-app-border-strong`} aria-label={s.label}>
              <span className="text-[10px] text-app-text-muted uppercase tracking-wider font-mono">{s.label}</span>
              <p className={`text-lg font-bold font-mono mt-0.5 ${s.color}`}>{s.value}</p>
            </div>
          ))}
        </div>

        {sections.map((s, i) => (
          <div key={s.title} className="animate-fadeIn" style={{ animationDelay: `${i * 80}ms` }}>
            <div className="bg-app-card border border-app-border rounded-xl overflow-hidden">
              <div className="px-4 sm:px-5 py-3 border-b border-app-border bg-app-card-alt">
                <h2 className="text-xs font-semibold text-app-text-secondary uppercase tracking-wider">{s.title}</h2>
              </div>
              <div>
                {s.entries.map(e => (
                  <Row key={e.key} label={e.label} value={e.value} />
                ))}
              </div>
            </div>
          </div>
        ))}
      </div>
    </main>
  );
}
