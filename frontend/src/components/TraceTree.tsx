import { useState } from 'react';
import type { TraceNode as TraceNodeType } from '../types/api';

interface Props {
  trace: TraceNodeType;
  depth?: number;
}

const NODE_COLORS: Record<string, { dot: string; border: string; bg: string }> = {
  satisfiable: { dot: 'bg-emerald-500', border: 'border-emerald-500/30', bg: 'bg-emerald-500/5' },
  unsatisfiable: { dot: 'bg-red-500', border: 'border-red-500/30', bg: 'bg-red-500/5' },
  unknown: { dot: 'bg-gray-500', border: 'border-gray-500/30', bg: 'bg-gray-500/5' },
};

function getNodeColors(nodeType: string) {
  return NODE_COLORS[nodeType] ?? NODE_COLORS.unknown;
}

function ConfidenceBar({ confidence }: { confidence: number }) {
  const hue = confidence > 0.7 ? 'emerald' : confidence > 0.4 ? 'amber' : 'red';
  const bgMap = { emerald: 'bg-emerald-500', amber: 'bg-amber-500', red: 'bg-red-500' };
  return (
    <div className="flex items-center gap-2 min-w-0">
      <div className="flex-1 h-1.5 bg-app-bg rounded-full overflow-hidden min-w-[48px] max-w-[100px]">
        <div
          className={`h-full rounded-full transition-all ${bgMap[hue]}`}
          style={{ width: `${Math.round(confidence * 100)}%` }}
        />
      </div>
      <span className="text-[10px] font-mono text-app-text-muted shrink-0 tabular-nums">
        {Math.round(confidence * 100)}%
      </span>
    </div>
  );
}

function SaliencyTokens({ tokens }: { tokens: string[] }) {
  if (!tokens || tokens.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1 mt-1.5">
      {tokens.map((token) => (
        <span
          key={token}
          className="inline-block px-1.5 py-0.5 rounded text-[10px] font-mono bg-amber-500/10 text-amber-400 border border-amber-500/20"
        >
          {token}
        </span>
      ))}
    </div>
  );
}

export default function TraceTree({ trace, depth = 0 }: Props) {
  const [collapsed, setCollapsed] = useState(false);
  const colors = getNodeColors(trace.node_type);
  const hasChildren = trace.children && trace.children.length > 0;

  return (
    <div className="select-none">
      <div
        className={`relative flex items-start gap-2 p-2.5 rounded-lg border transition-colors cursor-pointer hover:border-app-border-strong ${colors.bg} ${colors.border}`}
        style={{ marginLeft: depth * 20 }}
        onClick={() => setCollapsed((c) => !c)}
      >
        {hasChildren && (
          <span className="mt-0.5 text-[10px] text-app-text-muted shrink-0 w-3 text-center">
            {collapsed ? '▶' : '▼'}
          </span>
        )}
        {!hasChildren && <span className="mt-0.5 w-3 shrink-0" />}

        <div className="flex-1 min-w-0 space-y-1">
          <div className="flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full shrink-0 ${colors.dot}`} />
            <span className="text-xs font-semibold text-app-text truncate">
              {trace.label}
            </span>
            <span className="text-[9px] uppercase tracking-wider text-app-text-muted font-mono shrink-0">
              {trace.node_type}
            </span>
          </div>

          {trace.confidence !== undefined && (
            <ConfidenceBar confidence={trace.confidence} />
          )}

          {trace.saliency_tokens && trace.saliency_tokens.length > 0 && (
            <SaliencyTokens tokens={trace.saliency_tokens} />
          )}
        </div>
      </div>

      {hasChildren && !collapsed && (
        <div className="mt-1 space-y-1">
          {trace.children!.map((child) => (
            <TraceTree key={child.label} trace={child} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
}
