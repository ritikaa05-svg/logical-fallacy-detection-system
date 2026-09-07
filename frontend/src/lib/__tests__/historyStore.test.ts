import { describe, it, expect, beforeEach } from 'vitest';
import {
  getHistory,
  addToHistory,
  saveLastAnalysis,
  getLastAnalysis,
  clearLastAnalysis,
} from '../historyStore';
import type { AnalysisResult } from '../../types/api';

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
});

function mockResult(overrides?: Partial<AnalysisResult>): AnalysisResult {
  return {
    version: '1.0.0',
    input_text: 'This is a test argument',
    is_logical_claim: true,
    salience_score: 0.8,
    coarse_category: 'logical',
    fine_labels: ['hasty_generalization'],
    confidence_scores: [0.85],
    salient_tokens: [],
    fallacies: [{ name: 'Hasty Generalization', quote: 'test', explanation: 'too broad', confidence: 0.85 }],
    argument_structure: null,
    cross_segment_contradictions: null,
    annotations: [],
    z3_status: null,
    correction_strategy: null,
    logic_score: 0.45,
    total_latency_ms: 1234,
    stage_latencies: { total: 1234 },
    cached: false,
    reranked: false,
    device_info: {},
    degradation_tier: 0,
    timestamp: new Date().toISOString(),
    ...overrides,
  };
}

describe('historyStore', () => {
  it('returns empty array when no history exists', () => {
    expect(getHistory()).toEqual([]);
  });

  it('stores and retrieves a history entry', () => {
    addToHistory(mockResult());
    const history = getHistory();
    expect(history).toHaveLength(1);
    expect(history[0].text).toBe('This is a test argument');
    expect(history[0].score).toBe(0.45);
    expect(history[0].fallacyCount).toBe(1);
    expect(history[0].latency).toBe(1234);
    expect(history[0].cached).toBe(false);
  });

  it('prepends new entries to the front', () => {
    addToHistory(mockResult({ input_text: 'first', logic_score: 0.8 }));
    addToHistory(mockResult({ input_text: 'second', logic_score: 0.3 }));
    const history = getHistory();
    expect(history).toHaveLength(2);
    expect(history[0].text).toBe('second');
    expect(history[1].text).toBe('first');
  });

  it('caches the cached flag', () => {
    addToHistory(mockResult({ cached: true }));
    expect(getHistory()[0].cached).toBe(true);
  });

  it('does not throw on corrupt localStorage', () => {
    localStorage.setItem('logiscan_analysis_history', '{corrupt');
    expect(getHistory()).toEqual([]);
  });

  it('stores full result and analysis id for recent entries', () => {
    addToHistory(mockResult({ analysis_id: 'abc123' }));
    const history = getHistory();
    expect(history[0].analysisId).toBe('abc123');
    expect(history[0].fullResult?.logic_score).toBe(0.45);
  });

  it('drops full result for entries beyond the keep window', () => {
    for (let i = 0; i < 12; i++) {
      addToHistory(mockResult({ input_text: `entry ${i}` }));
    }
    const history = getHistory();
    expect(history).toHaveLength(12);
    expect(history[0].fullResult).toBeDefined();
    expect(history[11].fullResult).toBeUndefined();
    expect(history[11].text).toBe('entry 0');
  });

  it('round-trips last analysis through sessionStorage', () => {
    const state = {
      mode: 'text' as const,
      text: 'hello world',
      result: mockResult(),
      uploadedDoc: null,
      docAnalysis: null,
      skipCache: false,
      fastTrack: true,
    };
    saveLastAnalysis(state);
    expect(getLastAnalysis()).toEqual(state);
    clearLastAnalysis();
    expect(getLastAnalysis()).toBeNull();
  });

  it('returns null for corrupt sessionStorage', () => {
    sessionStorage.setItem('logiscan_last_analysis', '{corrupt');
    expect(getLastAnalysis()).toBeNull();
  });
});
