export default function Metrics() {
  return (
    <main className="min-h-screen bg-app-bg">
      <div className="max-w-7xl mx-auto p-6 space-y-6">
        <h1 className="text-xl font-bold text-app-text">Metrics</h1>
        <p className="text-app-text-muted text-sm">
          Raw Prometheus metrics are available at the{' '}
          <a
            href="/metrics"
            className="text-amber-400 underline hover:text-amber-500"
            target="_blank"
            rel="noopener noreferrer"
          >
            /metrics
          </a>{' '}
          endpoint. Use Prometheus or a compatible collector to scrape them.
        </p>
      </div>
    </main>
  );
}
