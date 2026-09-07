import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

import Analysis from '../Analysis';
import type { AnalysisResult, DocumentAnalysisResult } from '../../types/api';

function makeResult(overrides: Partial<AnalysisResult> = {}): AnalysisResult {
  return {
    version: '2.0',
    input_text: 'This is a test argument with a logical flaw.',
    is_logical_claim: true,
    salience_score: 0.75,
    coarse_category: 'argument',
    fine_labels: ['hasty_generalization'],
    confidence_scores: [0.82],
    salient_tokens: [],
    fallacies: [
      {
        name: 'hasty_generalization',
        quote: 'Everyone from that town must be rude.',
        explanation: 'This is a hasty generalization based on insufficient evidence.',
        confidence: 0.82,
      },
    ],
    argument_structure: null,
    annotations: [
      {
        type: 'hasty_generalization',
        label: 'Hasty Generalization',
        confidence: 0.82,
        definition: 'A generalization based on insufficient evidence.',
        explanation: 'This claim is too broad.',
        sentence: '',
        sentence_start: 0,
        sentence_end: 44,
        spans: [{ text: 'Everyone from that town must be rude.', start: 0, end: 44, saliency: 0.9 }],
      },
    ],
    z3_status: null,
    correction_strategy: 'Provide more evidence to support your claim.',
    logic_score: 0.3,
    total_latency_ms: 1500,
    stage_latencies: { detector: 100, classifier: 200 },
    cached: false,
    reranked: false,
    device_info: {},
    degradation_tier: 0,
    timestamp: '2026-07-21T12:00:00Z',
    cross_segment_contradictions: {
      contradictions: [
        {
          segment_a_index: 0,
          segment_b_index: 1,
          segment_a_page: 1,
          segment_b_page: 2,
          type: 'semantic',
          description: 'The claims contradict each other.',
          severity: 'moderate',
          confidence: 0.75,
        },
      ],
      total_pairs_checked: 1,
      latency_ms: 50,
    },
    ...overrides,
  };
}

const mockDocResult: DocumentAnalysisResult = {
  document: {
    document_id: 'doc-abc',
    filename: 'test.pdf',
    mime_type: 'application/pdf',
    page_count: 3,
    char_count: 5000,
    text_preview: 'Preview...',
    pages: [
      { page_number: 1, text_preview: 'Page 1', start_offset: 0, end_offset: 100 },
      { page_number: 2, text_preview: 'Page 2', start_offset: 100, end_offset: 200 },
    ],
  },
  overall: makeResult({ input_text: 'Document analysis result.' }),
  per_page: [],
};

afterEach(() => {
  vi.restoreAllMocks();
  sessionStorage.clear();
});

describe('Analysis — Text Mode Rendering', () => {
  it('renders textarea and scan button', () => {
    render(<Analysis />);
    expect(screen.getByPlaceholderText('Paste a sentence or paragraph here...')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Analyze text' })).toBeTruthy();
  });

  it('renders mode tabs', () => {
    render(<Analysis />);
    expect(screen.getByText('Text')).toBeTruthy();
    expect(screen.getByText('Document')).toBeTruthy();
  });

  it('shows empty state prompt when idle with no result', () => {
    render(<Analysis />);
    expect(screen.getByText(/Enter text and press/i)).toBeTruthy();
  });

  it('disables scan button during loading', async () => {
    const fetchMock = vi.fn().mockReturnValue(new Promise(() => {}));
    vi.stubGlobal('fetch', fetchMock);
    render(<Analysis />);
    const textarea = screen.getByPlaceholderText('Paste a sentence or paragraph here...');
    fireEvent.change(textarea, { target: { value: 'Test argument with a flaw.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Analyze text' }));
    const scanningBtn = screen.getByRole('button', { name: 'Analyze text' });
    expect(scanningBtn).toBeTruthy();
    expect(scanningBtn).toBeDisabled();
    vi.unstubAllGlobals();
  });

  it('shows cancel button during loading', async () => {
    const fetchMock = vi.fn().mockReturnValue(new Promise(() => {}));
    vi.stubGlobal('fetch', fetchMock);
    render(<Analysis />);
    const textarea = screen.getByPlaceholderText('Paste a sentence or paragraph here...');
    fireEvent.change(textarea, { target: { value: 'Test argument.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Analyze text' }));
    expect(screen.getByText('Cancel')).toBeTruthy();
    vi.unstubAllGlobals();
  });

  it('shows error when clicking scan with empty input', () => {
    render(<Analysis />);
    const btn = screen.getByRole('button', { name: 'Analyze text' });
    fireEvent.click(btn);
    expect(screen.getByText(/Please enter at least 2 characters/)).toBeTruthy();
  });
});

describe('Analysis — Scan Flow', () => {
  it('performs successful scan and displays result', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true, json: () => Promise.resolve(makeResult()),
    });
    vi.stubGlobal('fetch', fetchMock);
    render(<Analysis />);
    const textarea = screen.getByPlaceholderText('Paste a sentence or paragraph here...');
    fireEvent.change(textarea, { target: { value: 'Test argument with a logical flaw.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Analyze text' }));
    await waitFor(() => { expect(screen.getByText(/Detected Fallacies/)).toBeTruthy(); });
    expect(screen.getByText('Hasty Generalization')).toBeTruthy();
    expect(screen.getByText(/Everyone from that town/)).toBeTruthy();
    vi.unstubAllGlobals();
  });

  it('displays logic score after successful scan', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true, json: () => Promise.resolve(makeResult({ logic_score: 0.3 })),
    });
    vi.stubGlobal('fetch', fetchMock);
    render(<Analysis />);
    const textarea = screen.getByPlaceholderText('Paste a sentence or paragraph here...');
    fireEvent.change(textarea, { target: { value: 'Test argument.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Analyze text' }));
    await waitFor(() => { expect(screen.getByText('Results')).toBeTruthy(); });
    expect(screen.getAllByText(/30%/).length).toBeGreaterThanOrEqual(1);
    vi.unstubAllGlobals();
  });

  it('shows degradation badge when degradation_tier > 0', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true, json: () => Promise.resolve(makeResult({ degradation_tier: 2 })),
    });
    vi.stubGlobal('fetch', fetchMock);
    render(<Analysis />);
    const textarea = screen.getByPlaceholderText('Paste a sentence or paragraph here...');
    fireEvent.change(textarea, { target: { value: 'Test argument.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Analyze text' }));
    await waitFor(() => { expect(screen.getByText('Results')).toBeTruthy(); });
    expect(screen.getByText('degraded (tier 2)')).toBeTruthy();
    vi.unstubAllGlobals();
  });

  it('does not show degradation badge at tier 0', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true, json: () => Promise.resolve(makeResult({ degradation_tier: 0 })),
    });
    vi.stubGlobal('fetch', fetchMock);
    render(<Analysis />);
    const textarea = screen.getByPlaceholderText('Paste a sentence or paragraph here...');
    fireEvent.change(textarea, { target: { value: 'Test argument.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Analyze text' }));
    await waitFor(() => { expect(screen.getByText('Results')).toBeTruthy(); });
    expect(screen.queryByText(/degraded \(tier/)).toBeNull();
    vi.unstubAllGlobals();
  });

  it('shows cross-segment contradictions', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true, json: () => Promise.resolve(makeResult()),
    });
    vi.stubGlobal('fetch', fetchMock);
    render(<Analysis />);
    const textarea = screen.getByPlaceholderText('Paste a sentence or paragraph here...');
    fireEvent.change(textarea, { target: { value: 'Test argument.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Analyze text' }));
    await waitFor(() => { expect(screen.getByText(/Cross-Segment Contradictions/)).toBeTruthy(); });
    expect(screen.getByText(/The claims contradict each other/)).toBeTruthy();
    vi.unstubAllGlobals();
  });

  it('labels paragraph contradictions as segments, not pages', async () => {
    const result = makeResult({
      cross_segment_contradictions: {
        contradictions: [
          {
            segment_a_index: 0,
            segment_b_index: 1,
            segment_a_page: null,
            segment_b_page: null,
            type: 'lexical',
            description: "Lexical contradiction: 'destroys' appears in segment A but 'creates' appears in segment B.",
            severity: 'moderate',
            confidence: 0.65,
          },
        ],
        total_pairs_checked: 1,
        latency_ms: 5,
      },
    });
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true, json: () => Promise.resolve(result),
    });
    vi.stubGlobal('fetch', fetchMock);
    render(<Analysis />);
    const textarea = screen.getByPlaceholderText('Paste a sentence or paragraph here...');
    fireEvent.change(textarea, { target: { value: 'Test argument.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Analyze text' }));
    await waitFor(() => { expect(screen.getByText(/Cross-Segment Contradictions/)).toBeTruthy(); });
    expect(screen.getByText('Segment 1 ↔ Segment 2')).toBeTruthy();
    expect(screen.queryByText(/Page \d+ ↔ Page \d+/)).toBeNull();
    expect(screen.queryByText(/View Page/)).toBeNull();
    vi.unstubAllGlobals();
  });

  it('shows error banner on API failure', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false, status: 500, json: () => Promise.resolve({ detail: 'Internal server error' }),
    });
    vi.stubGlobal('fetch', fetchMock);
    render(<Analysis />);
    const textarea = screen.getByPlaceholderText('Paste a sentence or paragraph here...');
    fireEvent.change(textarea, { target: { value: 'Test argument.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Analyze text' }));
    await waitFor(() => { expect(screen.getByText(/Internal server error/)).toBeTruthy(); });
    vi.unstubAllGlobals();
  });

  it('shows error banner on network error', async () => {
    const fetchMock = vi.fn().mockRejectedValue(new Error('Network error'));
    vi.stubGlobal('fetch', fetchMock);
    render(<Analysis />);
    const textarea = screen.getByPlaceholderText('Paste a sentence or paragraph here...');
    fireEvent.change(textarea, { target: { value: 'Test argument.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Analyze text' }));
    await waitFor(() => { expect(screen.getByText(/Network error/)).toBeTruthy(); });
    vi.unstubAllGlobals();
  });

  it('triggers scan on Ctrl+Enter', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true, json: () => Promise.resolve(makeResult()),
    });
    vi.stubGlobal('fetch', fetchMock);
    render(<Analysis />);
    const textarea = screen.getByPlaceholderText('Paste a sentence or paragraph here...');
    fireEvent.change(textarea, { target: { value: 'Test argument.' } });
    fireEvent.keyDown(textarea, { key: 'Enter', ctrlKey: true });
    await waitFor(() => { expect(screen.getByText(/Detected Fallacies/)).toBeTruthy(); });
    vi.unstubAllGlobals();
  });

  it('shows correction strategy after scan', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true, json: () => Promise.resolve(makeResult()),
    });
    vi.stubGlobal('fetch', fetchMock);
    render(<Analysis />);
    const textarea = screen.getByPlaceholderText('Paste a sentence or paragraph here...');
    fireEvent.change(textarea, { target: { value: 'Test argument.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Analyze text' }));
    await waitFor(() => { expect(screen.getByText('Correction')).toBeTruthy(); });
    expect(screen.getByText(/Provide more evidence/)).toBeTruthy();
    vi.unstubAllGlobals();
  });

  it('cancels scan when cancel button is clicked', async () => {
    const fetchMock = vi.fn().mockReturnValue(new Promise(() => {}));
    vi.stubGlobal('fetch', fetchMock);
    render(<Analysis />);
    const textarea = screen.getByPlaceholderText('Paste a sentence or paragraph here...');
    fireEvent.change(textarea, { target: { value: 'Test argument.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Analyze text' }));
    expect(screen.getByText('Cancel')).toBeTruthy();
    fireEvent.click(screen.getByText('Cancel'));
    expect(screen.queryByText('Cancel')).toBeNull();
    vi.unstubAllGlobals();
  });
});

describe('Analysis — Checkboxes', () => {
  it('shows skip cache checked by default', () => {
    render(<Analysis />);
    const cb = screen.getByRole('checkbox', { name: 'Skip Cache' }) as HTMLInputElement;
    expect(cb.checked).toBe(true);
  });

  it('toggles skip cache checkbox', () => {
    render(<Analysis />);
    const cb = screen.getByRole('checkbox', { name: 'Skip Cache' }) as HTMLInputElement;
    fireEvent.click(cb);
    expect(cb.checked).toBe(false);
    fireEvent.click(cb);
    expect(cb.checked).toBe(true);
  });

  it('shows fast track unchecked by default', () => {
    render(<Analysis />);
    const cb = screen.getByRole('checkbox', { name: 'Fast Track' }) as HTMLInputElement;
    expect(cb.checked).toBe(false);
  });

  it('toggles fast track checkbox', () => {
    render(<Analysis />);
    const cb = screen.getByRole('checkbox', { name: 'Fast Track' }) as HTMLInputElement;
    fireEvent.click(cb);
    expect(cb.checked).toBe(true);
    fireEvent.click(cb);
    expect(cb.checked).toBe(false);
  });
});

describe('Analysis — Document Mode', () => {
  it('switches to document mode and shows upload area', () => {
    render(<Analysis />);
    fireEvent.click(screen.getByText('Document'));
    expect(screen.getByText(/Upload Document/)).toBeTruthy();
    expect(screen.getByText(/Drag & drop or click to browse/i)).toBeTruthy();
  });

  it('performs document upload and analysis', async () => {
    const fetchMock = vi.fn((url: string) => {
      if (url.includes('/analyze')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(mockDocResult) });
      }
      return Promise.resolve({
        ok: true, json: () => Promise.resolve(mockDocResult.document),
      });
    });
    vi.stubGlobal('fetch', fetchMock);

    const { container } = render(<Analysis />);
    fireEvent.click(screen.getByText('Document'));

    const dropzone = container.querySelector('#file-upload-dropzone')!;
    const file = new File([new ArrayBuffer(1024)], 'report.pdf', { type: 'application/pdf' });
    fireEvent.drop(dropzone, { dataTransfer: { files: [file] } });

    fireEvent.click(screen.getByText('Upload & Analyze'));

    await waitFor(() => { expect(screen.getByText(/Detected Fallacies/)).toBeTruthy(); }, { timeout: 5000 });
    vi.unstubAllGlobals();
  });

  it('shows download buttons after document analysis', async () => {
    const fetchMock = vi.fn((url: string) => {
      if (url.includes('/analyze')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(mockDocResult) });
      }
      return Promise.resolve({
        ok: true, json: () => Promise.resolve(mockDocResult.document),
      });
    });
    vi.stubGlobal('fetch', fetchMock);

    const { container } = render(<Analysis />);
    fireEvent.click(screen.getByText('Document'));

    const dropzone = container.querySelector('#file-upload-dropzone')!;
    const file = new File([new ArrayBuffer(1024)], 'report.pdf', { type: 'application/pdf' });
    fireEvent.drop(dropzone, { dataTransfer: { files: [file] } });
    fireEvent.click(screen.getByText('Upload & Analyze'));

    await waitFor(() => { expect(screen.getByText('Download Report')).toBeTruthy(); }, { timeout: 5000 });
    fireEvent.click(screen.getByText('Download Report'));
    expect(screen.getByText('PDF Report')).toBeTruthy();
    expect(screen.getByText('JSON Report')).toBeTruthy();
    vi.unstubAllGlobals();
  });

  it('shows error on upload failure', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false, status: 413, json: () => Promise.resolve({ detail: 'File too large for server' }),
    });
    vi.stubGlobal('fetch', fetchMock);

    const { container } = render(<Analysis />);
    fireEvent.click(screen.getByText('Document'));

    const dropzone = container.querySelector('#file-upload-dropzone')!;
    const file = new File([new ArrayBuffer(1024)], 'report.pdf', { type: 'application/pdf' });
    fireEvent.drop(dropzone, { dataTransfer: { files: [file] } });
    fireEvent.click(screen.getByText('Upload & Analyze'));

    await waitFor(() => { expect(screen.getByText(/File too large for server/)).toBeTruthy(); }, { timeout: 5000 });
    vi.unstubAllGlobals();
  });
});
