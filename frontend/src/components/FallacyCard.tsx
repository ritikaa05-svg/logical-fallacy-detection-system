import { Link } from 'react-router-dom';
import type { FallacyDetail } from '../types/api';
import { FALLACY_COLORS } from '../lib/constants';

interface Props {
  fallacy: FallacyDetail;
  analysisId?: string;
}

function getAccent(name: string): string {
  const key = name.toLowerCase().replace(/\s+/g, '_');
  return FALLACY_COLORS[key]?.hex ?? '#F59E0B';
}

function confLabel(c: number): string {
  if (c > 0.8) return 'High';
  if (c > 0.5) return 'Medium';
  return 'Low';
}

function confColor(c: number): string {
  if (c > 0.8) return 'text-app-low';
  if (c > 0.5) return 'text-app-med';
  return 'text-app-text-muted';
}

export default function FallacyCard({ fallacy, analysisId }: Props) {
  const accent = getAccent(fallacy.name);
  return (
    <div
      className="bg-app-card border border-app-border rounded-lg p-3 sm:p-4 mb-2 transition-colors hover:border-app-border-strong overflow-hidden"
      style={{ borderLeft: `3px solid ${accent}` }}
      aria-label={`${fallacy.name.replace(/_/g, ' ')} - ${confLabel(fallacy.confidence)} confidence, ${Math.round(fallacy.confidence * 100)}%`}
    >
      <div className="flex items-center justify-between mb-1">
        <h4 className="text-sm font-bold uppercase tracking-wide" style={{ color: accent }}>
          {fallacy.name.replace(/_/g, ' ')}
        </h4>
        <span className={`text-xs sm:text-sm font-mono ${confColor(fallacy.confidence)}`}>
          {confLabel(fallacy.confidence)} &middot; {Math.round(fallacy.confidence * 100)}%
        </span>
      </div>
      <p className="text-xs text-app-text-secondary mb-1 break-words">
        &ldquo;{fallacy.quote}&rdquo;
      </p>
      <p className="text-xs text-app-text-muted break-words">
        {fallacy.explanation}
      </p>
      {analysisId && (
        <div className="mt-2 pt-2 border-t border-app-border">
          <Link
            to={`/traces/${analysisId}`}
            className="text-[10px] text-amber-400 hover:text-amber-300 transition-colors uppercase tracking-wider font-semibold"
          >
            &#8599; View Trace
          </Link>
        </div>
      )}
    </div>
  );
}
