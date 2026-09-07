import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { type ReactNode } from 'react';
import ErrorBoundary from '../components/ErrorBoundary';

interface MockPageProps {
  shouldThrow: boolean;
  text: string;
}

function MockPage({ shouldThrow, text }: MockPageProps): ReactNode {
  if (shouldThrow) throw new Error(`Intentional: ${text}`);
  return <div data-testid="page-content">{text}</div>;
}

const PAGE_NAMES = ['Analysis', 'Health', 'Status', 'History', 'TraceView'] as const;

describe('ErrorBoundary integration with page routes', () => {
  describe.each(PAGE_NAMES)('%s', (page) => {
    it('shows fallback UI when the page throws', () => {
      vi.spyOn(console, 'error').mockImplementation(() => {});
      render(
        <ErrorBoundary>
          <MockPage shouldThrow={true} text={page} />
        </ErrorBoundary>,
      );
      expect(screen.getByText('Something went wrong')).toBeTruthy();
      expect(screen.getByText(`Intentional: ${page}`)).toBeTruthy();
      expect(screen.getByText('Try again')).toBeTruthy();
      vi.restoreAllMocks();
    });

    it('recovers and re-renders after Try again is clicked when the page stops throwing', () => {
      vi.spyOn(console, 'error').mockImplementation(() => {});
      const { rerender } = render(
        <ErrorBoundary>
          <MockPage shouldThrow={true} text={page} />
        </ErrorBoundary>,
      );
      expect(screen.getByText('Something went wrong')).toBeTruthy();

      // Switch the child to a non-throwing state while error boundary still shows the fallback
      rerender(
        <ErrorBoundary>
          <MockPage shouldThrow={false} text={page} />
        </ErrorBoundary>,
      );
      // ErrorBoundary still has hasError=true from the first render
      expect(screen.getByText('Something went wrong')).toBeTruthy();

      // Click Try again to reset internal error state; children now render safely
      fireEvent.click(screen.getByText('Try again'));
      expect(screen.getByTestId('page-content')).toBeTruthy();
      expect(screen.getByText(page)).toBeTruthy();
      expect(screen.queryByText('Something went wrong')).toBeNull();
      vi.restoreAllMocks();
    });

    it('clears internal error state on resetKey change', () => {
      vi.spyOn(console, 'error').mockImplementation(() => {});
      const { rerender } = render(
        <ErrorBoundary resetKey={0}>
          <MockPage shouldThrow={true} text={page} />
        </ErrorBoundary>,
      );
      expect(screen.getByText('Something went wrong')).toBeTruthy();

      // Changing resetKey clears error state
      rerender(
        <ErrorBoundary resetKey={1}>
          <MockPage shouldThrow={false} text={page} />
        </ErrorBoundary>,
      );
      expect(screen.getByTestId('page-content')).toBeTruthy();
      expect(screen.getByText(page)).toBeTruthy();
      expect(screen.queryByText('Something went wrong')).toBeNull();
      vi.restoreAllMocks();
    });
  });
});
