import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import DebateDrawer from '../DebateDrawer';

function renderDrawer(open = true, onClose = vi.fn()) {
  return render(<DebateDrawer open={open} onClose={onClose} />);
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe('DebateDrawer', () => {
  it('renders welcome message when open', () => {
    renderDrawer();
    expect(screen.getByText(/Start a debate/i)).toBeTruthy();
  });

  it('does not render backdrop when closed', () => {
    const { container } = renderDrawer(false);
    const backdrop = container.querySelector('.fixed.inset-0');
    expect(backdrop).toBeNull();
  });

  it('renders backdrop when open', () => {
    const { container } = renderDrawer(true);
    const backdrop = container.querySelector('.fixed.inset-0');
    expect(backdrop).toBeTruthy();
  });

  it('calls onClose when backdrop is clicked', () => {
    const onClose = vi.fn();
    const { container } = renderDrawer(true, onClose);
    const backdrop = container.querySelector('.fixed.inset-0')!;
    fireEvent.click(backdrop);
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('calls onClose when Escape key is pressed', () => {
    const onClose = vi.fn();
    renderDrawer(true, onClose);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('calls onClose when close button is clicked', () => {
    const onClose = vi.fn();
    renderDrawer(true, onClose);
    fireEvent.click(screen.getByLabelText('Close debate'));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('has an input field and send button', () => {
    renderDrawer();
    expect(screen.getByPlaceholderText('Present your argument...')).toBeTruthy();
    expect(screen.getByText('Send')).toBeTruthy();
  });

  it('send button is initially enabled', () => {
    renderDrawer();
    expect(screen.getByText('Send')).not.toBeDisabled();
  });

  it('clear chat resets to welcome message', () => {
    renderDrawer();
    fireEvent.click(screen.getByText('Clear'));
    const welcomeMessages = screen.getAllByText(/Start a debate/i);
    expect(welcomeMessages).toHaveLength(1);
  });

  function submitForm(container: HTMLElement) {
    const form = container.querySelector('form')!;
    fireEvent.submit(form);
  }

  it('adds user message on submit', async () => {
    const fetchMock = vi.fn().mockRejectedValue(new Error('Network error'));
    vi.stubGlobal('fetch', fetchMock);

    const { container } = renderDrawer();
    const input = screen.getByPlaceholderText('Present your argument...');
    fireEvent.change(input, { target: { value: 'My argument' } });
    submitForm(container);

    await waitFor(() => {
      expect(screen.getByText('My argument')).toBeTruthy();
    });

    vi.unstubAllGlobals();
  });

  it('shows assistant message after successful API call', async () => {
    const mockResponse = {
      ok: true,
      json: () => Promise.resolve({
        session_id: 'test-session',
        agent_response: 'Good point, but consider...',
        agent_action: 'ASK_SOCRATIC',
        logic_score: 0.75,
        detected_fallacies: [],
      }),
    };
    const fetchMock = vi.fn().mockResolvedValue(mockResponse);
    vi.stubGlobal('fetch', fetchMock);

    const { container } = renderDrawer();
    const input = screen.getByPlaceholderText('Present your argument...');
    fireEvent.change(input, { target: { value: 'I think this is true' } });
    submitForm(container);

    act(() => { vi.advanceTimersByTime(500); });

    await waitFor(() => {
      expect(screen.getByText('Good point, but consider...')).toBeTruthy();
    });

    vi.unstubAllGlobals();
  });

  it('shows error message on API failure', async () => {
    const fetchMock = vi.fn().mockRejectedValue(new Error('Network error'));
    vi.stubGlobal('fetch', fetchMock);

    const { container } = renderDrawer();
    const input = screen.getByPlaceholderText('Present your argument...');
    fireEvent.change(input, { target: { value: 'My argument' } });
    submitForm(container);

    act(() => { vi.advanceTimersByTime(500); });

    await waitFor(() => {
      expect(screen.getByText(/Error: Network error/)).toBeTruthy();
    });

    vi.unstubAllGlobals();
  });

  it('shows action badge for assistant messages', async () => {
    const mockResponse = {
      ok: true,
      json: () => Promise.resolve({
        session_id: 'test-session',
        agent_response: 'Counter-argument here',
        agent_action: 'COUNTER_ARGUMENT',
        logic_score: 0.65,
        detected_fallacies: ['Hasty Generalization'],
      }),
    };
    const fetchMock = vi.fn().mockResolvedValue(mockResponse);
    vi.stubGlobal('fetch', fetchMock);

    const { container } = renderDrawer();
    const input = screen.getByPlaceholderText('Present your argument...');
    fireEvent.change(input, { target: { value: 'Test argument' } });
    submitForm(container);

    act(() => { vi.advanceTimersByTime(500); });

    await waitFor(() => {
      expect(screen.getByText('COUNTER ARGUMENT')).toBeTruthy();
    });

    vi.unstubAllGlobals();
  });

  it('shows logic score and fallacy count', async () => {
    const mockResponse = {
      ok: true,
      json: () => Promise.resolve({
        session_id: 'test-session',
        agent_response: 'Response here',
        agent_action: 'POINT_OUT_FALLACY',
        logic_score: 0.5,
        detected_fallacies: ['Hasty Generalization', 'Ad Hominem'],
      }),
    };
    const fetchMock = vi.fn().mockResolvedValue(mockResponse);
    vi.stubGlobal('fetch', fetchMock);

    const { container } = renderDrawer();
    const input = screen.getByPlaceholderText('Present your argument...');
    fireEvent.change(input, { target: { value: 'Another test' } });
    submitForm(container);

    act(() => { vi.advanceTimersByTime(500); });

    await waitFor(() => {
      expect(screen.getByText(/Score: 50%/)).toBeTruthy();
      expect(screen.getByText(/2 fallacies/)).toBeTruthy();
    });

    vi.unstubAllGlobals();
  });
});
