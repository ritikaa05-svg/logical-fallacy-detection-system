import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  getHistory,
  saveLastAnalysis,
  STORAGE_KEY,
  type HistoryEntry,
} from '../lib/historyStore';

function scoreColor(score: number): string {
  if (score >= 0.7) return 'text-app-high';
  if (score >= 0.4) return 'text-app-med';
  return 'text-app-low';
}

function scoreBarColor(score: number): string {
  if (score >= 0.7) return 'bg-app-high-bar';
  if (score >= 0.4) return 'bg-app-med-bar';
  return 'bg-app-low-bar';
}

export default function History() {
  const [entries, setEntries] = useState<HistoryEntry[]>([]);
  const navigate = useNavigate();

  useEffect(() => {
    setEntries(getHistory());
  }, []);

  const clearHistory = () => {
    localStorage.removeItem(STORAGE_KEY);
    setEntries([]);
  };

  const restoreEntry = (e: HistoryEntry) => {
    if (!e.fullResult) return;
    saveLastAnalysis({
      mode: 'text',
      text: e.fullResult.input_text,
      result: e.fullResult,
      uploadedDoc: null,
      docAnalysis: null,
      skipCache: false,
      fastTrack: false,
    });
    navigate('/');
  };

  return (
    <main className="min-h-screen bg-app-bg">
      <header className="bg-app-card border-b border-app-border px-4 sm:px-6 py-3">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <h1 className="text-sm font-bold text-app-text uppercase tracking-wider">Analysis History</h1>
          {entries.length > 0 && (
            <button onClick={clearHistory} className="text-xs text-app-text-muted hover:text-app-text-secondary transition-colors focus:outline-none focus:ring-2 focus:ring-amber-500 rounded" aria-label="Clear history">
              Clear
            </button>
          )}
        </div>
      </header>

      <div className="max-w-5xl mx-auto p-4 sm:p-6">
        {entries.length === 0 && (
          <div className="bg-app-card border border-app-border rounded-xl p-10 text-center">
            <p className="text-app-text-muted font-mono">No analyses yet. Run some scans to build history.</p>
          </div>
        )}

        <div className="space-y-2">
          {entries.map(e => {
            const clickable = Boolean(e.fullResult);
            const row = (
              <>
                <div className="flex items-center gap-4">
                  <div className={`text-lg font-bold font-mono ${scoreColor(e.score)}`}>
                    {Math.round(e.score * 100)}%
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-app-text truncate">{e.text}</p>
                    <div className="flex items-center gap-3 mt-1 text-[10px] text-app-text-muted font-mono">
                      <span>{new Date(e.timestamp).toLocaleString()}</span>
                      <span>{e.fallacyCount} fallac{e.fallacyCount === 1 ? 'y' : 'ies'}</span>
                      <span>{e.latency >= 1000 ? `${(e.latency / 1000).toFixed(1)}s` : `${e.latency}ms`}</span>
                      {e.cached && <span className="text-amber-500">cached</span>}
                    </div>
                  </div>
                  <div className="h-1.5 w-16 bg-app-bg rounded-full overflow-hidden border border-app-border shrink-0">
                    <div className={`h-full rounded-full ${scoreBarColor(e.score)}`} style={{ width: `${e.score * 100}%` }} />
                  </div>
                </div>
                {clickable && (
                  <span className="text-[10px] text-amber-400 font-semibold uppercase tracking-wider">
                    Click to restore
                  </span>
                )}
              </>
            );
            return clickable ? (
              <button
                key={e.id}
                onClick={() => restoreEntry(e)}
                className="w-full text-left bg-app-card border border-app-border rounded-xl p-4 transition-colors hover:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-500 cursor-pointer"
              >
                {row}
              </button>
            ) : (
              <div key={e.id} className="bg-app-card border border-app-border rounded-xl p-4">
                {row}
              </div>
            );
          })}
        </div>
      </div>
    </main>
  );
}
