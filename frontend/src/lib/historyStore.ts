import type { AnalysisResult, DocumentAnalysisResult, DocumentUploadResponse } from '../types/api';

export const STORAGE_KEY = 'logiscan_analysis_history';
export const LAST_ANALYSIS_KEY = 'logiscan_last_analysis';
const MAX_ENTRIES = 50;
const KEEP_FULL_RESULTS = 10;

export interface HistoryEntry {
  id: string;
  timestamp: string;
  text: string;
  score: number;
  fallacyCount: number;
  latency: number;
  cached: boolean;
  analysisId?: string;
  fullResult?: AnalysisResult;
}

export interface LastAnalysisState {
  mode: 'text' | 'document';
  text: string;
  result: AnalysisResult | null;
  uploadedDoc: DocumentUploadResponse | null;
  docAnalysis: DocumentAnalysisResult | null;
  skipCache: boolean;
  fastTrack: boolean;
}

export function getHistory(): HistoryEntry[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export function addToHistory(result: AnalysisResult): void {
  const entry: HistoryEntry = {
    id: crypto.randomUUID(),
    timestamp: new Date().toISOString(),
    text: result.input_text.slice(0, 200),
    score: result.logic_score,
    fallacyCount: result.fallacies.length,
    latency: result.total_latency_ms,
    cached: result.cached,
    analysisId: result.analysis_id,
    fullResult: result,
  };
  const history = getHistory();
  history.unshift(entry);
  try {
    const trimmed = history.slice(0, MAX_ENTRIES).map((e, i) =>
      i >= KEEP_FULL_RESULTS ? { ...e, fullResult: undefined } : e,
    );
    localStorage.setItem(STORAGE_KEY, JSON.stringify(trimmed));
  } catch {
    /* localStorage full */
  }
}

export function saveLastAnalysis(state: LastAnalysisState): void {
  try {
    sessionStorage.setItem(LAST_ANALYSIS_KEY, JSON.stringify(state));
  } catch {
    /* sessionStorage full */
  }
}

export function getLastAnalysis(): LastAnalysisState | null {
  try {
    const raw = sessionStorage.getItem(LAST_ANALYSIS_KEY);
    return raw ? (JSON.parse(raw) as LastAnalysisState) : null;
  } catch {
    return null;
  }
}

export function clearLastAnalysis(): void {
  try {
    sessionStorage.removeItem(LAST_ANALYSIS_KEY);
  } catch {
    /* ignore */
  }
}
