import { describe, it, expect, vi, beforeAll, afterEach } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Analysis from '../pages/Analysis';
import Health from '../pages/Health';
import Status from '../pages/Status';
import History from '../pages/History';
import type { HealthHistoryEntry, SystemHealth } from '../types/api';

beforeAll(() => {
  globalThis.ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
});

async function assertNoA11yViolations(container: HTMLElement): Promise<void> {
  const mod = await import('axe-core');
  const result = await mod.default.run(container);
  expect(result.violations).toHaveLength(0);
}

describe('Accessibility audit', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('Analysis page has no accessibility violations (idle state)', async () => {
    const { container } = render(
      <MemoryRouter>
        <Analysis />
      </MemoryRouter>,
    );
    await assertNoA11yViolations(container);
  });

  it('Health page has no accessibility violations (with data)', async () => {
    const mockData: HealthHistoryEntry[] = [
      { timestamp: new Date().toISOString(), score: 0.85 },
      { timestamp: new Date().toISOString(), score: 0.72 },
      { timestamp: new Date().toISOString(), score: 0.91 },
    ];
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockData),
    }));

    const { container } = render(
      <MemoryRouter>
        <Health />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(container.textContent).toContain('91%');
    }, { timeout: 5000 });

    await assertNoA11yViolations(container);
  });

  it('Status page has no accessibility violations (with data)', async () => {
    const mockHealth: SystemHealth = {
      status: 'healthy',
      version: '1.0.0',
      classifier_mode: 'Mock',
      device: { cpu: 'Apple M2', memory: '16 GB' },
      cache: { entries: 42, hit_rate: 0.85 },
      timestamp: new Date().toISOString(),
    };
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockHealth),
    }));

    const { container } = render(
      <MemoryRouter>
        <Status />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(container.textContent).toContain('Healthy');
    }, { timeout: 5000 });

    await assertNoA11yViolations(container);
  });

  it('History page has no accessibility violations (with entries)', async () => {
    const entries = [
      {
        id: '1',
        timestamp: new Date().toISOString(),
        text: 'Test analysis',
        score: 0.85,
        fallacyCount: 3,
        latency: 1200,
        cached: false,
      },
      {
        id: '2',
        timestamp: new Date().toISOString(),
        text: 'Another analysis',
        score: 0.45,
        fallacyCount: 1,
        latency: 800,
        cached: true,
      },
    ];
    localStorage.setItem('logiscan_analysis_history', JSON.stringify(entries));

    const { container } = render(
      <MemoryRouter>
        <History />
      </MemoryRouter>,
    );

    await assertNoA11yViolations(container);
  });
});
