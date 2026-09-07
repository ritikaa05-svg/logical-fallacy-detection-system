import { useMemo, type ReactNode } from 'react';
import type { FallacyAnnotation, TokenContribution, FallacySpan } from '../types/api';
import { FALLACY_COLORS } from '../lib/constants';

interface Props {
  text: string;
  annotations: FallacyAnnotation[] | null | undefined;
  salientTokens?: TokenContribution[] | null | undefined;
}

type EventType = 'S_START' | 'S_END' | 'T_START' | 'T_END';

interface SpanMeta {
  label: string;
  type: string;
  confidence: number;
  explanation: string;
  topToken: TokenContribution | undefined;
  accent: string;
}

interface SpanEvent {
  idx: number;
  type: EventType;
  meta?: SpanMeta;
  key: string;
}

export interface TextSeg {
  type: 'text';
  text: string;
}

export interface TreeNode {
  type: 'sentence' | 'trigger';
  children: (TreeNode | TextSeg)[];
  meta?: SpanMeta;
  id: string;
}



const CONFIDENCE_BG: Record<string, string> = {
  high: 'bg-red-50',
  medium: 'bg-amber-50',
  low: 'bg-slate-50',
};

function getAccent(type: string): string {
  const key = type.toLowerCase().replace(/\s+/g, '_');
  return FALLACY_COLORS[key]?.hex ?? '#F59E0B';
}

function getConfidenceKey(conf: number): 'high' | 'medium' | 'low' {
  if (conf >= 0.8) return 'high';
  if (conf >= 0.5) return 'medium';
  return 'low';
}

function getHighlightClasses(conf: number): { bg: string } {
  const key = getConfidenceKey(conf);
  return { bg: CONFIDENCE_BG[key] };
}

function getConfidenceTier(conf: number): { label: string; bg: string; text: string } {
  if (conf >= 0.8) return { label: 'High', bg: 'bg-red-100', text: 'text-red-700' };
  if (conf >= 0.5) return { label: 'Medium', bg: 'bg-amber-100', text: 'text-amber-700' };
  return { label: 'Low', bg: 'bg-slate-100', text: 'text-slate-500' };
}

function findTopToken(
  tokens: TokenContribution[] | null | undefined,
  span: FallacySpan,
): TokenContribution | undefined {
  if (!tokens) return undefined;
  return tokens
    .filter(t => t.start >= span.start && t.end <= span.end && t.score > 0)
    .sort((a, b) => b.score - a.score)[0];
}

export function buildEvents(
  text: string,
  annotations: FallacyAnnotation[],
  salientTokens: TokenContribution[] | null | undefined,
): SpanEvent[] {
  const events: SpanEvent[] = [];
  const textLen = text.length;

  for (let i = 0; i < annotations.length; i++) {
    const a = annotations[i];
    const ss = a.sentence_start;
    const se = a.sentence_end;
    if (ss != null && se != null && ss >= 0 && se <= textLen && ss < se) {
      events.push({ idx: ss, type: 'S_START', key: `s${i}` });
      events.push({ idx: se, type: 'S_END', key: `s${i}` });
    }

    for (const span of a.spans ?? []) {
      const { start, end } = span;
      if (start == null || end == null || start < 0 || end > textLen || start >= end) continue;
      const accent = getAccent(a.type);
      const topToken = findTopToken(salientTokens, span);
      events.push({
        idx: start,
        type: 'T_START',
        meta: {
          label: a.label,
          type: a.type,
          confidence: a.confidence,
          explanation: a.explanation,
          topToken,
          accent,
        },
        key: `t${i}-${start}`,
      });
      events.push({ idx: end, type: 'T_END', key: `t${i}-${start}` });
    }
  }

  const priority: Record<EventType, number> = { T_END: 0, S_END: 1, S_START: 2, T_START: 3 };
  events.sort((a, b) => a.idx - b.idx || priority[a.type] - priority[b.type]);
  return events;
}

export function buildTree(text: string, events: SpanEvent[]): (TreeNode | TextSeg)[] {
  const root: (TreeNode | TextSeg)[] = [];
  const stack: TreeNode[] = [];
  let lastIdx = 0;

  for (const ev of events) {
    const container = stack.length > 0 ? stack[stack.length - 1].children : root;

    if (ev.idx > lastIdx) {
      container.push({ type: 'text', text: text.slice(lastIdx, ev.idx) });
    }

    if (ev.type === 'T_START' || ev.type === 'S_START') {
      const node: TreeNode = {
        type: ev.type === 'T_START' ? 'trigger' : 'sentence',
        children: [],
        meta: ev.meta,
        id: ev.key,
      };
      container.push(node);
      stack.push(node);
    } else {
      const targetType = ev.type === 'T_END' ? 'trigger' : 'sentence';
      for (let i = stack.length - 1; i >= 0; i--) {
        if (stack[i].type === targetType && stack[i].id === ev.key) {
          stack.splice(i, 1);
          break;
        }
      }
    }

    lastIdx = ev.idx;
  }

  if (lastIdx < text.length) {
    const container = stack.length > 0 ? stack[stack.length - 1].children : root;
    container.push({ type: 'text', text: text.slice(lastIdx) });
  }

  return root;
}

function renderTree(nodes: (TreeNode | TextSeg)[]): ReactNode {
  const result: ReactNode[] = [];
  for (const n of nodes) {
    if (n.type === 'text') {
      result.push(n.text);
    } else if (n.type === 'sentence') {
      result.push(
        <span key={n.id} className="bg-blue-50 rounded-sm">
          {renderTree(n.children)}
        </span>,
      );
    } else if (n.type === 'trigger' && n.meta) {
      result.push(
        <TriggerSpan key={n.id} meta={n.meta}>
          {renderTree(n.children)}
        </TriggerSpan>,
      );
    }
  }
  return result;
}

function TriggerSpan({ meta, children }: { meta: SpanMeta; children: ReactNode }) {
  const hl = getHighlightClasses(meta.confidence);
  const accentHex = meta.accent;
  const tier = getConfidenceTier(meta.confidence);
  const pct = Math.round(meta.confidence * 100);

  return (
    <span className="relative inline cursor-help group">
        <span
          className={`font-semibold inline border-b-2 transition-colors duration-100 whitespace-pre-wrap ${hl.bg}`}
          style={{ borderColor: accentHex }}
        >
          {children}
        </span>

      <span className={`
        absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2
        pointer-events-none group-hover:pointer-events-auto
        invisible group-hover:visible
        opacity-0 group-hover:opacity-100
        transition-all duration-150 trigger-tooltip
      `}>
        <span className="absolute top-full left-0 w-full h-2.5 bg-transparent" />

        <span className="block bg-white border border-slate-200 rounded-xl shadow-lg p-4 w-80 max-w-[85vw] text-left leading-normal">
          <span className="flex items-center justify-between mb-2">
            <span className="text-xs font-extrabold uppercase tracking-wider" style={{ color: accentHex }}>
              {meta.label}
            </span>
            <span className={`text-xs px-2 py-0.5 rounded-full font-sans ${tier.bg} ${tier.text}`}>
              {tier.label} &middot; {pct}%
            </span>
          </span>

          {meta.topToken && (
            <span className="block text-xs text-slate-500 italic mb-2 font-sans">
              Top token: &ldquo;<span className="font-medium text-slate-700 not-italic">{meta.topToken.token}</span>&rdquo;
            </span>
          )}

          <span className="block text-sm text-slate-600 border-t border-slate-100 pt-2 mt-1 font-sans">
            {meta.explanation}
          </span>
        </span>
      </span>
    </span>
  );
}

export default function AnnotatedText({ text, annotations, salientTokens }: Props) {
  const elements = useMemo(() => {
    const anns = annotations ?? [];
    const events = buildEvents(text, anns, salientTokens ?? null);
    const tree = buildTree(text, events);
    return renderTree(tree);
  }, [text, annotations, salientTokens]);

  return (
    <div
      role="textbox"
      aria-readonly="true"
      aria-label="Annotated text content"
      tabIndex={0}
      className="text-base leading-[2.1] text-gray-900 bg-[#faf8f0] p-6 rounded-xl border border-[#e8e4d8] whitespace-pre-wrap break-words shadow-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
    >
      {elements}
    </div>
  );
}
