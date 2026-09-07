import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import History from '../History';
import { getLastAnalysis } from '../../lib/historyStore';

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
});

function renderHistory() {
  return render(
    <MemoryRouter>
      <History />
    </MemoryRouter>,
  );
}

function seedHistory() {
  const entries = [
    { id: '1', timestamp: '2026-01-01T12:00:00.000Z', text: 'First argument', score: 0.85, fallacyCount: 2, latency: 500, cached: false },
    { id: '2', timestamp: '2026-01-02T12:00:00.000Z', text: 'Second argument', score: 0.45, fallacyCount: 1, latency: 1500, cached: true },
    { id: '3', timestamp: '2026-01-03T12:00:00.000Z', text: 'Third argument', score: 0.15, fallacyCount: 3, latency: 100, cached: false },
  ];
  localStorage.setItem('logiscan_analysis_history', JSON.stringify(entries));
}

describe('History page', () => {
  it('shows empty state when no entries', () => {
    renderHistory();
    expect(screen.getByText(/No analyses yet/i)).toBeTruthy();
  });

  it('renders stored history entries', () => {
    seedHistory();
    renderHistory();
    expect(screen.getByText('First argument')).toBeTruthy();
    expect(screen.getByText('Second argument')).toBeTruthy();
    expect(screen.getByText('Third argument')).toBeTruthy();
  });

  it('shows score percentages', () => {
    seedHistory();
    renderHistory();
    expect(screen.getByText('85%')).toBeTruthy();
    expect(screen.getByText('45%')).toBeTruthy();
    expect(screen.getByText('15%')).toBeTruthy();
  });

  it('shows cached indicator', () => {
    seedHistory();
    renderHistory();
    const cached = screen.getAllByText('cached');
    expect(cached).toHaveLength(1);
  });

  it('shows fallacy count', () => {
    seedHistory();
    renderHistory();
    expect(screen.getByText('2 fallacies')).toBeTruthy();
    expect(screen.getByText('1 fallacy')).toBeTruthy();
    expect(screen.getByText('3 fallacies')).toBeTruthy();
  });

  it('formats latency correctly', () => {
    seedHistory();
    renderHistory();
    expect(screen.getByText('500ms')).toBeTruthy();
    expect(screen.getByText('1.5s')).toBeTruthy();
    expect(screen.getByText('100ms')).toBeTruthy();
  });

  it('clear button removes all entries', () => {
    seedHistory();
    renderHistory();
    fireEvent.click(screen.getByText('Clear'));
    expect(screen.getByText(/No analyses yet/i)).toBeTruthy();
  });

  it('has no clear button when history is empty', () => {
    renderHistory();
    expect(screen.queryByText('Clear')).toBeNull();
  });

  it('restores a full result when a clickable row is clicked', () => {
    const fullResult = {
      version: '1.0.0',
      input_text: 'Full analysis text',
      is_logical_claim: true,
      salience_score: 0.8,
      coarse_category: 'logical',
      fine_labels: ['ad_hominem'],
      confidence_scores: [0.9],
      salient_tokens: [],
      fallacies: [],
      argument_structure: null,
      cross_segment_contradictions: null,
      annotations: [],
      z3_status: null,
      correction_strategy: null,
      logic_score: 0.85,
      total_latency_ms: 500,
      stage_latencies: { total: 500 },
      cached: false,
      reranked: false,
      device_info: {},
    degradation_tier: 0,
      timestamp: new Date().toISOString(),
    };
    localStorage.setItem(
      'logiscan_analysis_history',
      JSON.stringify([
        {
          id: '1',
          timestamp: '2026-01-01T12:00:00.000Z',
          text: 'Full analysis text',
          score: 0.85,
          fallacyCount: 0,
          latency: 500,
          cached: false,
          analysisId: 'trace-1',
          fullResult,
        },
      ]),
    );
    renderHistory();
    fireEvent.click(screen.getByText('Full analysis text'));
    const restored = getLastAnalysis();
    expect(restored?.result?.logic_score).toBe(0.85);
    expect(restored?.text).toBe('Full analysis text');
  });

  it('does not make rows without a full result clickable', () => {
    seedHistory();
    renderHistory();
    expect(screen.queryByText('Click to restore')).toBeNull();
  });
});
