import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import TraceTree from '../components/TraceTree';
import type { TraceResponse } from '../types/api';

function Skeleton() {
  return (
    <div className="animate-pulse space-y-3">
      {[1, 2, 3].map((i) => (
        <div
          key={i}
          className="bg-app-card border border-app-border rounded-lg p-4"
          style={{ marginLeft: (i - 1) * 20 }}
        >
          <div className="h-4 bg-app-card-alt rounded w-1/3 mb-2" />
          <div className="h-2 bg-app-card-alt rounded w-1/2" />
        </div>
      ))}
    </div>
  );
}

export default function TraceView() {
  const { analysisId } = useParams<{ analysisId: string }>();
  const [data, setData] = useState<TraceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!analysisId) return;
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetch(`/api/v1/traces/${analysisId}`)
      .then((res) => {
        if (!res.ok) throw new Error(`Request failed (${res.status})`);
        return res.json() as Promise<TraceResponse>;
      })
      .then((json) => {
        if (!cancelled) {
          setData(json);
          setLoading(false);
        }
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : 'Failed to load trace');
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [analysisId]);

  return (
    <main className="min-h-screen bg-app-bg">
      <div className="max-w-4xl mx-auto p-4 sm:p-6 space-y-4">
        <div className="flex items-center gap-3">
          <Link
            to="/"
            className="text-xs text-amber-400 hover:text-amber-300 transition-colors"
          >
            &larr; Back to Analysis
          </Link>
          <h1 className="text-sm font-bold text-app-text uppercase tracking-wider">
            Trace View
          </h1>
          {analysisId && (
            <span className="text-[10px] font-mono text-app-text-muted truncate">
              {analysisId}
            </span>
          )}
        </div>

        {loading && <Skeleton />}

        {error && (
          <div className="bg-[var(--badge-red-bg)] border border-[var(--badge-red-border)] text-[var(--badge-red-text)] rounded-xl p-4 text-sm">
            {error}
          </div>
        )}

        {data && (
          <div className="bg-app-card border border-app-border rounded-xl p-4 sm:p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xs font-semibold text-app-text-secondary uppercase tracking-wider">
                Symbolic Trace
              </h2>
              {data.analysis_id && (
                <span className="text-[10px] font-mono text-app-text-muted">
                  ID: {data.analysis_id}
                </span>
              )}
            </div>
            <TraceTree trace={data.trace_tree} />
          </div>
        )}

        {!loading && !error && !data && (
          <div className="bg-app-card border border-app-border rounded-xl p-10 text-center">
            <p className="text-app-text-muted text-sm">No trace data available.</p>
          </div>
        )}
      </div>
    </main>
  );
}
