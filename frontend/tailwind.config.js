/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    screens: {
      'sm': '640px',
      'md': '768px',
      'lg': '1024px',
      'xl': '1280px',
      '2xl': '1536px',
    },
    extend: {
      fontFamily: {
        mono: ['ui-monospace', 'SFMono-Regular', '"Fira Code"', '"Cascadia Code"', 'Menlo', 'Consolas', 'monospace'],
      },
      colors: {
        app: {
          bg: 'var(--app-bg)',
          card: 'var(--app-card)',
          'card-alt': 'var(--app-card-alt)',
          'card-hover': 'var(--app-card-hover)',
          border: 'var(--app-border)',
          'border-strong': 'var(--app-border-strong)',
          text: 'var(--app-text)',
          'text-secondary': 'var(--app-text-secondary)',
          'text-muted': 'var(--app-text-muted)',
          'input-bg': 'var(--app-input-bg)',
          'input-border': 'var(--app-input-border)',
          placeholder: 'var(--app-placeholder)',
          high: 'var(--app-high)',
          med: 'var(--app-med)',
          low: 'var(--app-low)',
          'high-bar': 'var(--app-high-bar)',
          'med-bar': 'var(--app-med-bar)',
          'low-bar': 'var(--app-low-bar)',
          green: 'var(--app-green)',
          'green-bg': 'var(--app-green-bg)',
        },
      },
    },
  },
  plugins: [],
};
