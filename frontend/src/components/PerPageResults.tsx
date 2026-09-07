import { useState } from 'react';
import FallacyCard from './FallacyCard';
import type { PerPageResult } from '../types/api';

interface Props {
  pages: PerPageResult[];
}

function scoreColor(score: number): string {
  if (score >= 0.7) return 'text-app-high';
  if (score >= 0.4) return 'text-app-med';
  return 'text-app-low';
}

function scoreBg(score: number): string {
  if (score >= 0.7) return 'bg-[var(--badge-green-bg)] border-[var(--badge-green-border)]';
  if (score >= 0.4) return 'bg-[var(--badge-amber-bg)] border-[var(--badge-amber-border)]';
  return 'bg-[var(--badge-red-bg)] border-[var(--badge-red-border)]';
}

export default function PerPageResults({ pages }: Props) {
  const [expandedPage, setExpandedPage] = useState<number | null>(null);

  if (!pages || pages.length === 0) {
    return (
      <div className="bg-app-card border border-app-border rounded-xl p-6 text-center">
        <p className="text-app-text-muted text-sm">No per-page results available.</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <h3 className="text-xs font-semibold text-app-text-secondary uppercase tracking-wider">
        Per-Page Breakdown ({pages.length} pages)
      </h3>

      {/* Horizontal scrollable summary strip */}
      <div
        id="per-page-results-strip"
        className="flex gap-2 overflow-x-auto pb-2 snap-x snap-mandatory"
        role="list"
        aria-label="Per-page analysis results"
      >
        {pages.map(({ page_number, result }) => {
          const isExpanded = expandedPage === page_number;
          const score = result.logic_score;
          const fallacyCount = result.fallacies.length;

          return (
            <button
              key={page_number}
              id={`page-result-${page_number}`}
              role="listitem"
              onClick={() => setExpandedPage(isExpanded ? null : page_number)}
              className={[
                'flex-shrink-0 snap-start rounded-lg border px-3 py-2.5 text-left',
                'transition-all duration-150 cursor-pointer min-w-[100px]',
                isExpanded
                  ? scoreBg(score) + ' ring-2 ring-amber-500/50'
                  : 'bg-app-card border-app-border hover:border-app-border-strong',
              ].join(' ')}
              aria-pressed={isExpanded}
              aria-label={`Page ${page_number}: logic score ${Math.round(score * 100)}%, ${fallacyCount} fallacies`}
            >
              <div className="text-[10px] text-app-text-muted uppercase tracking-wider mb-1">
                Page {page_number}
              </div>
              <div className={`text-sm sm:text-base font-bold font-mono ${scoreColor(score)}`}>
                {Math.round(score * 100)}%
              </div>
              <div className="text-[10px] text-app-text-muted mt-0.5">
                {fallacyCount} {fallacyCount === 1 ? 'fallacy' : 'fallacies'}
              </div>
            </button>
          );
        })}
      </div>

      {/* Expanded page detail */}
      {expandedPage !== null && (() => {
        const pageResult = pages.find((p) => p.page_number === expandedPage);
        if (!pageResult) return null;
        const { result } = pageResult;

        return (
          <div
            id={`page-detail-${expandedPage}`}
            className={`rounded-xl border p-4 animate-fadeIn ${scoreBg(result.logic_score)}`}
          >
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-sm font-bold text-app-text">
                Page {expandedPage} — Full Results
              </h4>
              <button
                onClick={() => setExpandedPage(null)}
                className="text-app-text-muted hover:text-app-text-secondary transition-colors"
                aria-label="Close page detail"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Quick stats */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 mb-3">
              <div className="bg-app-bg/60 rounded-lg border border-app-border/60 p-2">
                <div className="text-[9px] text-app-text-muted uppercase tracking-wider">Score</div>
                <div className={`text-sm font-bold font-mono ${scoreColor(result.logic_score)}`}>
                  {Math.round(result.logic_score * 100)}%
                </div>
              </div>
              <div className="bg-app-bg/60 rounded-lg border border-app-border/60 p-2">
                <div className="text-[9px] text-app-text-muted uppercase tracking-wider">Category</div>
                <div className="text-xs font-semibold text-app-text truncate">
                  {result.coarse_category || '—'}
                </div>
              </div>
              <div className="bg-app-bg/60 rounded-lg border border-app-border/60 p-2">
                <div className="text-[9px] text-app-text-muted uppercase tracking-wider">Z3</div>
                <div className="text-xs font-semibold font-mono text-app-text">
                  {result.z3_status || '—'}
                </div>
              </div>
            </div>

            {/* Fallacy cards */}
            {result.fallacies.length > 0 ? (
              <div className="space-y-1">
                {result.fallacies.map((f, i) => (
                  <FallacyCard key={`${f.name}-${i}`} fallacy={f} analysisId={result.analysis_id} />
                ))}
              </div>
            ) : (
              <p className="text-xs text-app-text-muted italic">
                No fallacies detected on this page.
              </p>
            )}

            {/* Correction */}
            {result.correction_strategy && (
              <div className="mt-3 bg-[var(--badge-green-bg)] border border-[var(--badge-green-border)] rounded-lg p-3">
                <p className="text-xs text-[var(--badge-green-text)]">{result.correction_strategy}</p>
              </div>
            )}
          </div>
        );
      })()}
    </div>
  );
}
