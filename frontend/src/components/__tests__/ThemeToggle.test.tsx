import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import ThemeToggle from '../ThemeToggle';

beforeEach(() => {
  localStorage.clear();
  document.documentElement.classList.remove('light');
});

describe('ThemeToggle', () => {
  it('renders with default dark terminal label', () => {
    render(<ThemeToggle />);
    expect(screen.getByText('[ light ]')).toBeTruthy();
  });

  it('toggles to light theme on click', () => {
    render(<ThemeToggle />);
    fireEvent.click(screen.getByText('[ light ]'));
    expect(screen.getByText('[ terminal ]')).toBeTruthy();
    expect(document.documentElement.classList.contains('light')).toBe(true);
  });

  it('toggles back to dark on second click', () => {
    render(<ThemeToggle />);
    fireEvent.click(screen.getByText('[ light ]'));
    fireEvent.click(screen.getByText('[ terminal ]'));
    expect(screen.getByText('[ light ]')).toBeTruthy();
    expect(document.documentElement.classList.contains('light')).toBe(false);
  });

  it('persists preference to localStorage', () => {
    render(<ThemeToggle />);
    fireEvent.click(screen.getByText('[ light ]'));
    expect(localStorage.getItem('theme')).toBe('light');
  });
});
