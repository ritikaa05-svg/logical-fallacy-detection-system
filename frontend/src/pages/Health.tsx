import { useState, useEffect } from 'react';
import {
  Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Area, AreaChart,
} from 'recharts';
import { showToast } from '../lib/toast';
import type { HealthHistoryEntry } from '../types/api';

export default function Health() {
  const [data, setData] = useState<HealthHistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const fetchHistory = async () => {
      try {
        const res = await fetch('/api/v1/history');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json: HealthHistoryEntry[] = await res.json();
        if (!cancelled) setData(json.slice(-10));
      } catch (err: unknown) {
        if (!cancelled) {
          const msg = err instanceof Error ? err.message : 'Failed to load';
          setError(msg);
          showToast(msg);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchHistory();
    return () => { cancelled = true; };
  }, []);

  const chartData = data.map((d, i) => ({
    turn: i + 1,
    score: Math.round(d.score * 100),
    time: new Date(d.timestamp).toLocaleTimeString(),
  }));

  const latest = data.length > 0 ? Math.round(data[data.length - 1].score * 100) : 0;
  const avg = data.length > 0
    ? Math.round(data.reduce((s, d) => s + d.score, 0) / data.length * 100)
    : 0;
  const maxVal = data.length > 0 ? Math.round(Math.max(...data.map(d => d.score)) * 100) : 0;
  const minVal = data.length > 0 ? Math.round(Math.min(...data.map(d => d.score)) * 100) : 0;
  const trend = data.length >= 2
    ? data[data.length - 1].score - data[data.length - 2].score
    : 0;

  const scoreColor = (v: number) => v >= 70 ? 'text-app-high' : v >= 40 ? 'text-app-med' : 'text-app-low';

  return (
    <main className="min-h-screen bg-app-bg">
      <header className="bg-app-card border-b border-app-border px-4 sm:px-6 py-3">
        <div className="max-w-5xl mx-auto">
          <h1 className="text-sm font-bold text-app-text uppercase tracking-wider">Logic Health</h1>
        </div>
      </header>

      <div className="max-w-5xl mx-auto p-4 sm:p-6 space-y-4 sm:space-y-6">
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          {[
            { label: 'Latest', value: `${latest}%`, color: scoreColor(latest) },
            { label: 'Average', value: `${avg}%`, color: scoreColor(avg) },
            {
              label: 'Trend',
              value: `${trend > 0 ? '+' : ''}${Math.round(trend * 100)}%`,
              color: trend > 0 ? 'text-app-high' : trend < 0 ? 'text-app-low' : 'text-app-text-secondary',
            },
            { label: 'Highest', value: `${maxVal}%`, color: 'text-app-high' },
            { label: 'Lowest', value: `${minVal}%`, color: 'text-app-low' },
          ].map(s => (
            <div key={s.label} className="bg-app-card border border-app-border rounded-xl p-4 transition-colors hover:border-app-border-strong">
              <span className="text-[10px] text-app-text-muted uppercase tracking-wider font-mono">{s.label}</span>
              <p className={`text-xl font-bold font-mono mt-0.5 ${s.color}`}>{s.value}</p>
            </div>
          ))}
        </div>

        <div className="bg-app-card border border-app-border rounded-xl p-4 sm:p-6">
          <h2 className="text-xs font-semibold text-app-text-secondary uppercase tracking-wider mb-4">Logic Score Trend (last 10)</h2>

          {loading && (
            <div className="h-64 flex items-center justify-center">
              <div className="animate-pulse h-4 bg-app-card-alt rounded w-32" />
            </div>
          )}

          {error && (
            <div className="h-64 flex items-center justify-center text-app-low text-sm font-mono">{error}</div>
          )}

          {!loading && !error && chartData.length === 0 && (
            <div className="h-64 flex items-center justify-center text-app-text-muted text-sm font-mono">
              No data yet. Run some analyses to build history.
            </div>
          )}

          {!loading && !error && chartData.length > 0 && (
            <ResponsiveContainer width="100%" height={320} aria-label="Health status chart" role="img">
              <AreaChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 5 }}>
                <defs>
                  <linearGradient id="scoreGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#d97706" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#d97706" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--app-border)" />
                <XAxis
                  dataKey="turn"
                  tick={{ fontSize: 11, fill: 'var(--app-text-muted)', fontFamily: 'monospace' }}
                  axisLine={{ stroke: 'var(--app-border-strong)' }}
                />
                <YAxis
                  domain={[0, 100]}
                  tick={{ fontSize: 11, fill: 'var(--app-text-muted)', fontFamily: 'monospace' }}
                  axisLine={{ stroke: 'var(--app-border-strong)' }}
                />
                <Tooltip
                  contentStyle={{
                    background: 'var(--app-card)',
                    border: '1px solid var(--app-border)',
                    borderRadius: '8px',
                    fontSize: '12px',
                    fontFamily: 'monospace',
                    color: 'var(--app-text)',
                  }}
                  labelFormatter={(label) => `Analysis #${label}`}
                  formatter={(value) => [`${value}%`, 'Score']}
                />
                <Area type="monotone" dataKey="score" stroke="#d97706" strokeWidth={2} fill="url(#scoreGradient)" />
                <Line
                  type="monotone"
                  dataKey="score"
                  stroke="#d97706"
                  strokeWidth={2}
                  dot={{ r: 3, fill: '#d97706', strokeWidth: 0 }}
                  activeDot={{ r: 5, fill: '#d97706', strokeWidth: 2, stroke: 'var(--app-bg)' }}
                  animationDuration={800}
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>
    </main>
  );
}
