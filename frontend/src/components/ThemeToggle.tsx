import { useEffect, useState } from 'react';

export default function ThemeToggle() {
  const [light, setLight] = useState(() => {
    if (typeof window === 'undefined') return false;
    const stored = localStorage.getItem('theme');
    if (stored) return stored === 'light';
    return false;
  });

  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle('light', light);
    localStorage.setItem('theme', light ? 'light' : 'dark');
  }, [light]);

  return (
    <button
      onClick={() => setLight(prev => !prev)}
      className="text-xs text-app-text-muted hover:text-app-text-secondary transition-colors font-mono focus:outline-none focus:ring-2 focus:ring-amber-500 rounded"
      aria-label="Toggle theme"
      aria-pressed={light}
    >
      {light ? '[ terminal ]' : '[ light ]'}
    </button>
  );
}
