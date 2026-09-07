import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import AnnotatedText from '../AnnotatedText';
import { buildEvents, buildTree, type TreeNode } from '../AnnotatedText';
import type { FallacyAnnotation, TokenContribution } from '../../types/api';

const sampleText = 'The quick brown fox jumps over the lazy dog.';

function mkAnnotation(overrides: Partial<FallacyAnnotation>): FallacyAnnotation {
  return {
    type: 'hasty_generalization',
    label: 'Hasty Generalization',
    confidence: 0.85,
    definition: 'A generalization based on insufficient evidence.',
    explanation: 'This claim is too broad.',
    sentence: '',
    sentence_start: -1,
    sentence_end: -1,
    spans: [],
    ...overrides,
  };
}

function mkToken(text: string, start: number, end: number, score: number): TokenContribution {
  return { token: text, start, end, score };
}

// --- Unit tests: buildEvents / buildTree ---

describe('buildEvents', () => {
  it('returns empty array for empty annotations', () => {
    const events = buildEvents('hello', [], []);
    expect(events).toEqual([]);
  });

  it('creates S_START and S_END for sentence spans', () => {
    const ann = mkAnnotation({ sentence_start: 4, sentence_end: 9 });
    const events = buildEvents('The quick brown fox', [ann], []);
    const start = events.find(e => e.type === 'S_START');
    const end = events.find(e => e.type === 'S_END');
    expect(start).toBeDefined();
    expect(start!.idx).toBe(4);
    expect(end).toBeDefined();
    expect(end!.idx).toBe(9);
  });

  it('creates T_START and T_END for trigger spans', () => {
    const ann = mkAnnotation({
      spans: [{ text: 'quick', start: 4, end: 9, saliency: 0.9 }],
    });
    const events = buildEvents('The quick brown fox', [ann], []);
    const ts = events.find(e => e.type === 'T_START');
    const te = events.find(e => e.type === 'T_END');
    expect(ts).toBeDefined();
    expect(ts!.idx).toBe(4);
    expect(te).toBeDefined();
    expect(te!.idx).toBe(9);
  });

  it('prioritizes T_END < S_END < S_START < T_START at same index', () => {
    const ann = mkAnnotation({
      sentence_start: 5,
      sentence_end: 10,
      spans: [{ text: 'quick', start: 5, end: 10, saliency: 0.9 }],
    });
    const events = buildEvents('xxxxxquickxxxx', [ann], []);
    // At idx=5: S_START and T_START both at idx 5
    // T_START should come after S_START per priority
    // At idx=10: S_END and T_END both at idx 10
    // T_END should come before S_END
    const sStart = events.findIndex(e => e.type === 'S_START');
    const tStart = events.findIndex(e => e.type === 'T_START');
    const sEnd = events.findIndex(e => e.type === 'S_END');
    const tEnd = events.findIndex(e => e.type === 'T_END');
    expect(tEnd).toBeLessThan(sEnd);
    expect(sStart).toBeLessThan(tStart);
  });

  it('skips invalid spans', () => {
    const ann = mkAnnotation({
      spans: [
        { text: 'invalid', start: -1, end: 5, saliency: 0 },
        { text: 'valid', start: 0, end: 3, saliency: 0.5 },
      ],
    });
    const events = buildEvents('abcdef', [ann], []);
    const validSpans = events.filter(e => e.type === 'T_START');
    expect(validSpans).toHaveLength(1);
    expect(validSpans[0].idx).toBe(0);
  });

  it('finds top salient token for each span', () => {
    const tokens = [
      mkToken('brown', 10, 15, 0.5),
      mkToken('quick', 4, 9, 0.9),
      mkToken('fox', 16, 19, 0.3),
    ];
    const ann = mkAnnotation({
      spans: [{ text: 'quick brown fox', start: 4, end: 19, saliency: 0.9 }],
    });
    const events = buildEvents(sampleText, [ann], tokens);
    const tStart = events.find(e => e.type === 'T_START')!;
    expect(tStart.meta?.topToken?.token).toBe('quick');
  });
});

describe('buildTree', () => {
  it('returns text-only root for no events', () => {
    const tree = buildTree('hello', []);
    expect(tree).toHaveLength(1);
    expect(tree[0]).toEqual({ type: 'text', text: 'hello' });
  });

  it('produces trigger node for single span', () => {
    const ann = mkAnnotation({
      spans: [{ text: 'quick', start: 4, end: 9, saliency: 0.9 }],
    });
    const events = buildEvents('The quick brown fox', [ann], []);
    const tree = buildTree('The quick brown fox', events);
    expect(tree.length).toBeGreaterThanOrEqual(3);
    const triggerNode = tree.find(
      (n): n is TreeNode & { type: 'trigger' } =>
        'type' in n && n.type === 'trigger',
    );
    expect(triggerNode).toBeDefined();
  });

  it('appends trailing text after last event', () => {
    const ann = mkAnnotation({
      spans: [{ text: 'quick', start: 4, end: 9, saliency: 0.9 }],
    });
    const events = buildEvents('The quick brown fox', [ann], []);
    const tree = buildTree('The quick brown fox', events);
    const last = tree[tree.length - 1];
    expect(last).toEqual({ type: 'text', text: ' brown fox' });
  });
});

// --- Integration tests: render output ---

describe('AnnotatedText (rendered)', () => {
  it('renders plain text when no annotations', () => {
    render(<AnnotatedText text="Hello world" annotations={null} />);
    expect(screen.getByText('Hello world')).toBeTruthy();
  });

  it('renders plain text when annotations is empty array', () => {
    render(<AnnotatedText text="Hello world" annotations={[]} />);
    expect(screen.getByText('Hello world')).toBeTruthy();
  });

  it('highlights a trigger span', () => {
    const anns: FallacyAnnotation[] = [
      mkAnnotation({
        label: 'Hasty Generalization',
        sentence_start: 0,
        sentence_end: 44,
        spans: [{ text: 'lazy', start: 35, end: 39, saliency: 0.9 }],
      }),
    ];
    const { container } = render(<AnnotatedText text={sampleText} annotations={anns} />);
    const trigger = container.querySelector('.cursor-help');
    expect(trigger).toBeTruthy();
  });

  it('renders tooltip content inside trigger span', () => {
    const anns: FallacyAnnotation[] = [
      mkAnnotation({
        label: 'Hasty Generalization',
        confidence: 0.85,
        explanation: 'Too broad a claim.',
        sentence_start: 0,
        sentence_end: 44,
        spans: [{ text: 'lazy', start: 35, end: 39, saliency: 0.9 }],
      }),
    ];
    const { container } = render(<AnnotatedText text={sampleText} annotations={anns} />);
    expect(container.textContent).toContain('Hasty Generalization');
    expect(container.textContent).toContain('Too broad a claim.');
  });

  it('renders top salient token in tooltip', () => {
    const tokens: TokenContribution[] = [
      mkToken('lazy', 35, 39, 0.95),
    ];
    const anns: FallacyAnnotation[] = [
      mkAnnotation({
        label: 'Hasty Generalization',
        sentence_start: 0,
        sentence_end: 44,
        spans: [{ text: 'lazy', start: 35, end: 39, saliency: 0.9 }],
      }),
    ];
    const { container } = render(
      <AnnotatedText text={sampleText} annotations={anns} salientTokens={tokens} />,
    );
    expect(container.textContent).toContain('lazy');
  });

  it('shows confidence tier and percentage', () => {
    const anns: FallacyAnnotation[] = [
      mkAnnotation({
        label: 'Hasty Generalization',
        confidence: 0.85,
        sentence_start: 0,
        sentence_end: 44,
        spans: [{ text: 'lazy', start: 35, end: 39, saliency: 0.9 }],
      }),
    ];
    const { container } = render(<AnnotatedText text={sampleText} annotations={anns} />);
    expect(container.textContent).toMatch(/High.*85%/);
  });

  it('renders multiple annotations', () => {
    const anns: FallacyAnnotation[] = [
      mkAnnotation({
        label: 'Hasty Generalization',
        sentence_start: 0,
        sentence_end: 14,
        spans: [{ text: 'The quick', start: 0, end: 8, saliency: 0.9 }],
        type: 'hasty_generalization',
      }),
      mkAnnotation({
        label: 'Red Herring',
        sentence_start: 15,
        sentence_end: 44,
        spans: [{ text: 'lazy dog', start: 35, end: 43, saliency: 0.7 }],
        type: 'red_herring',
      }),
    ];
    const { container } = render(<AnnotatedText text={sampleText} annotations={anns} />);
    expect(container.textContent).toContain('Hasty Generalization');
    expect(container.textContent).toContain('Red Herring');
  });
});
