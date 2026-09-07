import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import PerPageResults from '../PerPageResults';
import type { PerPageResult } from '../../types/api';

const baseResult = {
  version: '2.0',
  input_text: '',
  is_logical_claim: true,
  salience_score: 0.8,
  coarse_category: null,
  fine_labels: [],
  confidence_scores: [],
  salient_tokens: [],
  fallacies: [],
  argument_structure: null,
  annotations: [],
  z3_status: null,
  correction_strategy: null,
  logic_score: 0,
  total_latency_ms: 0,
  stage_latencies: {},
  cached: false,
  reranked: false,
  device_info: {},
  degradation_tier: 0,
  timestamp: '',
  cross_segment_contradictions: null,
};

const mockPages: PerPageResult[] = [
  {
    page_number: 1,
    result: {
      ...baseResult,
      logic_score: 0.85,
      coarse_category: 'argument',
      z3_status: 'valid',
      fallacies: [
        {
          name: 'hasty_generalization',
          quote: 'Everyone must be rude.',
          explanation: 'Too broad a claim.',
          confidence: 0.85,
        },
        {
          name: 'straw_man',
          quote: 'You are misrepresenting the argument.',
          explanation: 'Misrepresentation detected.',
          confidence: 0.72,
        },
      ],
    },
  },
  {
    page_number: 2,
    result: {
      ...baseResult,
      input_text: 'Second page of text.',
      logic_score: 0.35,
      coarse_category: 'non-argument',
      z3_status: null,
      fallacies: [
        {
          name: 'red_herring',
          quote: 'Changing the subject.',
          explanation: 'Irrelevant point introduced.',
          confidence: 0.6,
        },
      ],
    },
  },
  {
    page_number: 3,
    result: {
      ...baseResult,
      input_text: 'Third page.',
      logic_score: 0.92,
      fallacies: [],
    },
  },
];

describe('PerPageResults', () => {
  it('renders page buttons with correct numbers', () => {
    render(<PerPageResults pages={mockPages} />);
    expect(screen.getByText('Page 1')).toBeTruthy();
    expect(screen.getByText('Page 2')).toBeTruthy();
    expect(screen.getByText('Page 3')).toBeTruthy();
  });

  it('displays score percentages', () => {
    render(<PerPageResults pages={mockPages} />);
    expect(screen.getByText('85%')).toBeTruthy();
    expect(screen.getByText('35%')).toBeTruthy();
    expect(screen.getByText('92%')).toBeTruthy();
  });

  it('displays fallacy counts', () => {
    render(<PerPageResults pages={mockPages} />);
    expect(screen.getByText('2 fallacies')).toBeTruthy();
    expect(screen.getByText('1 fallacy')).toBeTruthy();
    expect(screen.getByText('0 fallacies')).toBeTruthy();
  });

  it('expands detail panel when a page button is clicked', () => {
    render(<PerPageResults pages={mockPages} />);
    const page1Btn = screen.getByLabelText(/Page 1: logic score 85%/);
    fireEvent.click(page1Btn);
    expect(screen.getByText('Page 1 — Full Results')).toBeTruthy();
    expect(screen.getByText(/Too broad a claim/)).toBeTruthy();
    expect(screen.getByText(/Misrepresentation detected/)).toBeTruthy();
  });

  it('closes detail panel when clicking the close button', () => {
    render(<PerPageResults pages={mockPages} />);
    const page1Btn = screen.getByLabelText(/Page 1: logic score 85%/);
    fireEvent.click(page1Btn);
    expect(screen.getByText('Page 1 — Full Results')).toBeTruthy();

    const closeBtn = screen.getByLabelText('Close page detail');
    fireEvent.click(closeBtn);
    expect(screen.queryByText('Page 1 — Full Results')).toBeNull();
  });

  it('shows correction strategy in detail panel when present', () => {
    const pagesWithCorrection: PerPageResult[] = [
      {
        page_number: 1,
        result: {
          ...baseResult,
          logic_score: 0.4,
          correction_strategy: 'Consider providing more evidence for this claim.',
          fallacies: [{ name: 'false_cause', quote: 'A causes B.', explanation: 'Causal oversimplification.', confidence: 0.7 }],
        },
      },
    ];
    render(<PerPageResults pages={pagesWithCorrection} />);
    const page1Btn = screen.getByLabelText(/Page 1: logic score 40%/);
    fireEvent.click(page1Btn);
    expect(screen.getByText(/Consider providing more evidence/)).toBeTruthy();
  });

  it('shows empty state when pages array is empty', () => {
    render(<PerPageResults pages={[]} />);
    expect(screen.getByText(/No per-page results available/)).toBeTruthy();
  });

  it('shows no fallacies message when page has no fallacies', () => {
    render(<PerPageResults pages={mockPages} />);
    const page3Btn = screen.getByLabelText(/Page 3: logic score 92%/);
    fireEvent.click(page3Btn);
    expect(screen.getByText('No fallacies detected on this page.')).toBeTruthy();
  });

  it('renders FallacyCard for each fallacy in expanded page', () => {
    render(<PerPageResults pages={mockPages} />);
    const page1Btn = screen.getByLabelText(/Page 1: logic score 85%/);
    fireEvent.click(page1Btn);
    expect(screen.getByText(/hasty generalization/i)).toBeTruthy();
    expect(screen.getByText(/straw man/i)).toBeTruthy();
  });
});
