import { Component, type ReactNode, type ErrorInfo } from 'react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  resetKey?: number | string;
}

interface State {
  hasError: boolean;
  error: Error | null;
  prevResetKey?: number | string;
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null, prevResetKey: undefined };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  static getDerivedStateFromProps(props: Props, state: State): Partial<State> | null {
    if (props.resetKey !== state.prevResetKey) {
      return { hasError: false, error: null, prevResetKey: props.resetKey };
    }
    return null;
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('ErrorBoundary caught:', error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback || (
        <main className="min-h-screen bg-app-bg flex items-center justify-center p-6">
          <div className="bg-app-card border border-app-border rounded-xl p-8 max-w-lg text-center">
            <p className="text-app-low text-lg font-bold font-mono mb-2">Something went wrong</p>
            <p className="text-app-text-muted text-sm font-mono mb-4">{this.state.error?.message}</p>
            <button
              onClick={() => this.setState({ hasError: false, error: null })}
              className="bg-amber-600 hover:bg-amber-500 text-black font-bold py-2 px-6 rounded-lg text-sm uppercase tracking-wider transition-colors"
            >
              Try again
            </button>
          </div>
        </main>
      );
    }
    return this.props.children;
  }
}
