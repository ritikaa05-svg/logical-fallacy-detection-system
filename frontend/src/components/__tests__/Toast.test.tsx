import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import Toast from '../Toast';
import { showToast } from '../../lib/toast';

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe('Toast', () => {
  it('renders nothing when no toasts emitted', () => {
    const { container } = render(<Toast />);
    expect(container.innerHTML).toBe('');
  });

  it('shows info toast with message', () => {
    render(<Toast />);
    act(() => { showToast('Operation saved', 'info'); });
    expect(screen.getByText('Operation saved')).toBeTruthy();
  });

  it('shows error toast with message', () => {
    render(<Toast />);
    act(() => { showToast('Something broke', 'error'); });
    expect(screen.getByText('Something broke')).toBeTruthy();
  });

  it('auto-dismisses a toast after 5 seconds', () => {
    render(<Toast />);
    act(() => { showToast('Will disappear', 'info'); });
    expect(screen.getByText('Will disappear')).toBeTruthy();
    act(() => { vi.advanceTimersByTime(5000); });
    expect(screen.queryByText('Will disappear')).toBeNull();
  });

  it('stacks multiple toasts', () => {
    render(<Toast />);
    act(() => { showToast('First', 'info'); });
    act(() => { showToast('Second', 'error'); });
    act(() => { showToast('Third', 'info'); });
    expect(screen.getByText('First')).toBeTruthy();
    expect(screen.getByText('Second')).toBeTruthy();
    expect(screen.getByText('Third')).toBeTruthy();
    expect(screen.getAllByText('×')).toHaveLength(3);
  });

  it('dismisses a toast when close button is clicked', () => {
    render(<Toast />);
    act(() => { showToast('Dismiss me', 'info'); });
    expect(screen.getByText('Dismiss me')).toBeTruthy();
    const closeBtn = screen.getByText('×');
    act(() => { fireEvent.click(closeBtn); });
    expect(screen.queryByText('Dismiss me')).toBeNull();
  });

  it('only dismisses the clicked toast, not others', () => {
    render(<Toast />);
    act(() => { showToast('Keep me', 'info'); });
    act(() => { showToast('Remove me', 'error'); });
    const closeButtons = screen.getAllByText('×');
    expect(closeButtons).toHaveLength(2);
    act(() => { fireEvent.click(closeButtons[1]); });
    expect(screen.getByText('Keep me')).toBeTruthy();
    expect(screen.queryByText('Remove me')).toBeNull();
  });
});
