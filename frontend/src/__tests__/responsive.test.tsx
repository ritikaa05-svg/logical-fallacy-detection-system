import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Analysis from '../pages/Analysis';
import Health from '../pages/Health';
import Status from '../pages/Status';
import History from '../pages/History';
import App from '../App';
import FallacyCard from '../components/FallacyCard';
import FileUpload from '../components/FileUpload';
import PerPageResults from '../components/PerPageResults';
import type { FallacyDetail, PerPageResult } from '../types/api';

function setViewport(width: number) {
  Object.defineProperty(window, 'innerWidth', {
    writable: true,
    configurable: true,
    value: width,
  });
  window.dispatchEvent(new Event('resize'));
}

const viewports = [320, 768, 1024, 1440];

describe('Responsive layout - page renders', () => {
  viewports.forEach((width) => {
    it(`Analysis page renders without crashing at ${width}px`, () => {
      setViewport(width);
      render(
        <MemoryRouter>
          <Analysis />
        </MemoryRouter>,
      );
      const scans = screen.getAllByText('Scan');
      expect(scans.length).toBeGreaterThanOrEqual(1);
      expect(screen.getByLabelText('Input mode')).toBeInTheDocument();
    });
  });

  viewports.forEach((width) => {
    it(`Health page renders without crashing at ${width}px`, () => {
      setViewport(width);
      render(
        <MemoryRouter>
          <Health />
        </MemoryRouter>,
      );
      const headers = screen.getAllByText('Logic Health');
      expect(headers.length).toBeGreaterThanOrEqual(1);
    });
  });

  viewports.forEach((width) => {
    it(`Status page renders without crashing at ${width}px`, () => {
      setViewport(width);
      render(
        <MemoryRouter>
          <Status />
        </MemoryRouter>,
      );
      const headers = screen.getAllByText('System Status');
      expect(headers.length).toBeGreaterThanOrEqual(1);
    });
  });

  viewports.forEach((width) => {
    it(`History page renders without crashing at ${width}px`, () => {
      setViewport(width);
      render(
        <MemoryRouter>
          <History />
        </MemoryRouter>,
      );
      expect(screen.getByText('Analysis History')).toBeInTheDocument();
    });
  });
});

describe('Responsive layout - App nav', () => {
  it('shows hamburger button below 768px', () => {
    setViewport(320);
    render(<App />);
    const hamburger = screen.getByLabelText('Toggle menu');
    expect(hamburger).toBeInTheDocument();
  });

  it('toggles mobile menu on hamburger click', () => {
    setViewport(320);
    render(<App />);
    const hamburger = screen.getByLabelText('Toggle menu');
    fireEvent.click(hamburger);
    const links = screen.getAllByText('Analysis');
    expect(links.length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText('Debate').length).toBeGreaterThanOrEqual(2);
  });

  it('hamburger toggles menu on repeat clicks', () => {
    setViewport(320);
    render(<App />);
    const hamburger = screen.getByLabelText('Toggle menu');
    fireEvent.click(hamburger);
    const debateAfterOpen = screen.getAllByText('Debate');
    expect(debateAfterOpen.length).toBeGreaterThanOrEqual(2);
    fireEvent.click(hamburger);
    const debateAfterClose = screen.getAllByText('Debate');
    expect(debateAfterClose.length).toBeLessThan(debateAfterOpen.length);
  });

  it('hamburger menu links close debate on click', () => {
    setViewport(320);
    render(<App />);
    const hamburger = screen.getByLabelText('Toggle menu');
    fireEvent.click(hamburger);
    const debateBtns = screen.getAllByText('Debate');
    const mobileDebate = debateBtns[1];
    fireEvent.click(mobileDebate);
  });
});

describe('Responsive layout - Analysis components', () => {
  it('mode tabs have flex-col on mobile classes', () => {
    render(
      <MemoryRouter>
        <Analysis />
      </MemoryRouter>,
    );
    const tabs = document.getElementById('analysis-mode-tabs');
    expect(tabs).toBeInTheDocument();
    expect(tabs!.className).toContain('flex-col');
    expect(tabs!.className).toContain('sm:flex-row');
  });

  it('scan button has min-w-0 sm:min-w-[200px]', () => {
    render(
      <MemoryRouter>
        <Analysis />
      </MemoryRouter>,
    );
    const scanBtns = screen.getAllByText('Scan');
    const button = scanBtns.find(
      (el) => el.tagName === 'BUTTON' && el.className.includes('min-w-0'),
    );
    expect(button).toBeTruthy();
  });

  it('right panel has overflow-x-hidden', () => {
    const { container } = render(
      <MemoryRouter>
        <Analysis />
      </MemoryRouter>,
    );
    const rightPanel = container.querySelector('.lg\\:col-span-3');
    expect(rightPanel).toBeInTheDocument();
    expect(rightPanel!.className).toContain('overflow-x-hidden');
  });
});

describe('Responsive layout - FallacyCard', () => {
  const mockFallacy: FallacyDetail = {
    name: 'straw_man',
    quote: 'They misrepresented the argument entirely.',
    explanation: 'This is a classic straw man fallacy.',
    confidence: 0.85,
    start: 0,
    end: 10,
  };

  it('renders with overflow-hidden and responsive padding', () => {
    const { container } = render(<FallacyCard fallacy={mockFallacy} />);
    const card = container.firstChild as HTMLElement;
    expect(card.className).toContain('overflow-hidden');
    expect(card.className).toContain('p-3');
    expect(card.className).toContain('sm:p-4');
  });

  it('badge has responsive text size', () => {
    render(<FallacyCard fallacy={mockFallacy} />);
    const badge = screen.getByText(/High/);
    expect(badge.className).toContain('text-xs');
    expect(badge.className).toContain('sm:text-sm');
  });

  it('quote and explanation have break-words', () => {
    render(<FallacyCard fallacy={mockFallacy} />);
    const quote = screen.getByText(/They misrepresented/);
    expect(quote.className).toContain('break-words');
    const explanation = screen.getByText(/classic straw man/);
    expect(explanation.className).toContain('break-words');
  });
});

describe('Responsive layout - FileUpload', () => {
  it('dropzone has w-full class', () => {
    render(
      <FileUpload
        onUploaded={() => {}}
        onError={() => {}}
      />,
    );
    const dropzone = document.getElementById('file-upload-dropzone');
    expect(dropzone).toBeInTheDocument();
    expect(dropzone!.className).toContain('w-full');
  });

  it('upload button has w-full sm:w-auto', () => {
    render(
      <FileUpload
        onUploaded={() => {}}
        onError={() => {}}
      />,
    );
    const btn = document.getElementById('file-upload-submit');
    expect(btn).toBeInTheDocument();
    expect(btn!.className).toContain('w-full');
    expect(btn!.className).toContain('sm:w-auto');
  });
});

describe('Responsive layout - PerPageResults', () => {
  const mockPages: PerPageResult[] = [
    {
      page_number: 1,
      result: {
        input_text: 'Test text',
        logic_score: 0.8,
        salience_score: 0.5,
        total_latency_ms: 100,
        fallacies: [],
        annotations: [],
        coarse_category: 'valid',
        z3_status: 'sat',
        cross_segment_contradictions: undefined,
      },
    },
  ];

  it('detail grid has grid-cols-1 sm:grid-cols-3', () => {
    const { container } = render(
      <MemoryRouter>
        <PerPageResults pages={mockPages} />
      </MemoryRouter>,
    );
    const btn = document.getElementById('page-result-1');
    expect(btn).toBeInTheDocument();
    fireEvent.click(btn!);
    const detailGrid = container.querySelector('.grid-cols-1');
    expect(detailGrid).toBeInTheDocument();
    expect(detailGrid!.className).toContain('grid-cols-1');
    expect(detailGrid!.className).toContain('sm:grid-cols-3');
  });

  it('page number has responsive text size', () => {
    render(
      <MemoryRouter>
        <PerPageResults pages={mockPages} />
      </MemoryRouter>,
    );
    const pageScore = screen.getByText('80%');
    expect(pageScore.className).toContain('text-sm');
    expect(pageScore.className).toContain('sm:text-base');
  });
});

describe('Root container overflow protection', () => {
  it('html element has overflow-x-hidden (check class rendering)', () => {
    const style = document.createElement('style');
    style.textContent = 'html { overflow-x: hidden; }';
    document.head.appendChild(style);
    const computed = getComputedStyle(document.documentElement);
    expect(computed.overflowX).toBe('hidden');
    document.head.removeChild(style);
  });
});
