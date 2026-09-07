import { lazy, Suspense, useState } from 'react';
import { BrowserRouter, Routes, Route, NavLink, useLocation } from 'react-router-dom';
import DebateDrawer from './components/DebateDrawer';
import ThemeToggle from './components/ThemeToggle';
import ErrorBoundary from './components/ErrorBoundary';
import Toast from './components/Toast';

const Analysis = lazy(() => import('./pages/Analysis'));
const Health = lazy(() => import('./pages/Health'));
const Status = lazy(() => import('./pages/Status'));
const History = lazy(() => import('./pages/History'));
const TraceView = lazy(() => import('./pages/TraceView'));
const Metrics = lazy(() => import('./pages/Metrics'));

function NotFound() {
  return (
    <main className="min-h-screen bg-app-bg flex items-center justify-center">
      <div className="text-center">
        <h1 className="text-4xl font-bold text-app-text mb-2">404</h1>
        <p className="text-app-text-muted">Page not found.</p>
      </div>
    </main>
  );
}

const links = [
  { to: '/', label: 'Analysis' },
  { to: '/health', label: 'Health' },
  { to: '/status', label: 'Status' },
  { to: '/history', label: 'History' },
];

function PageShell({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  return (
    <div key={location.pathname} className="animate-slideUp">
      {children}
    </div>
  );
}

function Skeleton() {
  return (
    <main className="min-h-screen bg-app-bg">
      <div className="max-w-7xl mx-auto p-6 space-y-4">
        <div className="h-8 bg-app-card-alt rounded w-48 animate-pulse" />
        <div className="h-64 bg-app-card rounded-xl border border-app-border animate-pulse" />
      </div>
    </main>
  );
}

export default function App() {
  const [debateOpen, setDebateOpen] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <BrowserRouter>
      <nav className="bg-app-card border-b border-app-border px-4 sm:px-6">
        <div className="max-w-7xl mx-auto flex items-center gap-4 sm:gap-6 h-11">
          <span className="text-sm font-bold text-amber-500 tracking-wider mr-2 sm:mr-4 shrink-0">
            LogiScan
          </span>

          <div className="hidden md:flex items-center gap-4 sm:gap-6">
            {links.map(link => (
              <NavLink
                key={link.to}
                to={link.to}
                end={link.to === '/'}
                className={({ isActive }) =>
                  `text-xs uppercase tracking-wider transition-colors shrink-0 ${
                    isActive
                      ? 'text-amber-400 border-b-2 border-amber-500 h-11 flex items-center'
                      : 'text-app-text-muted hover:text-app-text-secondary'
                  }`
                }
              >
                {link.label}
              </NavLink>
            ))}

            <button
              onClick={() => setDebateOpen(true)}
              className="text-xs uppercase tracking-wider text-app-text-muted hover:text-app-text-secondary transition-colors shrink-0"
            >
              Debate
            </button>
          </div>

          <div className="ml-auto shrink-0 flex items-center gap-2">
            <ThemeToggle />
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="md:hidden text-app-text-muted hover:text-app-text-secondary transition-colors p-1"
              aria-label="Toggle menu"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                {mobileMenuOpen ? (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                ) : (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                )}
              </svg>
            </button>
          </div>
        </div>

        {mobileMenuOpen && (
          <div className="md:hidden border-t border-app-border py-2 space-y-1">
            {links.map(link => (
              <NavLink
                key={link.to}
                to={link.to}
                end={link.to === '/'}
                onClick={() => setMobileMenuOpen(false)}
                className={({ isActive }) =>
                  `block px-4 py-2 text-xs uppercase tracking-wider transition-colors ${
                    isActive ? 'text-amber-400 bg-app-card-alt' : 'text-app-text-muted hover:text-app-text-secondary'
                  }`
                }
              >
                {link.label}
              </NavLink>
            ))}
            <button
              onClick={() => { setDebateOpen(true); setMobileMenuOpen(false); }}
              className="w-full text-left px-4 py-2 text-xs uppercase tracking-wider text-app-text-muted hover:text-app-text-secondary transition-colors"
            >
              Debate
            </button>
          </div>
        )}
      </nav>

      <Suspense fallback={<Skeleton />}>
        <PageShell>
          <Routes>
            <Route path="/" element={<ErrorBoundary><Analysis /></ErrorBoundary>} />
            <Route path="/health" element={<ErrorBoundary><Health /></ErrorBoundary>} />
            <Route path="/status" element={<ErrorBoundary><Status /></ErrorBoundary>} />
            <Route path="/history" element={<ErrorBoundary><History /></ErrorBoundary>} />
            <Route path="/traces/:analysisId" element={<ErrorBoundary><TraceView /></ErrorBoundary>} />
            {/* Metrics page — references the /metrics Prometheus endpoint; kept for admin visibility */}
            <Route path="/metrics" element={<ErrorBoundary><Metrics /></ErrorBoundary>} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </PageShell>
      </Suspense>

      <DebateDrawer open={debateOpen} onClose={() => setDebateOpen(false)} />
      <Toast />
    </BrowserRouter>
  );
}
