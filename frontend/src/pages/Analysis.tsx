import { useState, useRef, useCallback, useEffect } from 'react';
import AnnotatedText from '../components/AnnotatedText';
import FallacyCard from '../components/FallacyCard';
import FileUpload from '../components/FileUpload';
import PerPageResults from '../components/PerPageResults';
import { addToHistory, getLastAnalysis, saveLastAnalysis } from '../lib/historyStore';
import { validateAnalysisResult } from '../lib/validation';
import type {
  AnalysisResult,
  DocumentUploadResponse,
  DocumentAnalysisResult,
  ContradictionMatch,
} from '../types/api';

const API_URL = '/api/v1/analyze';
const DOC_ANALYZE_URL = (id: string) => `/api/v1/documents/${id}/analyze`;
const DOC_REPORT_URL = (id: string, fmt: string) =>
  `/api/v1/documents/${id}/report?format=${fmt}`;

type InputMode = 'text' | 'document';

function SeverityBadge({ severity }: { severity: ContradictionMatch['severity'] }) {
  const colors = {
    critical: 'bg-[var(--badge-red-bg)] text-[var(--badge-red-text)] border-[var(--badge-red-border)]',
    moderate: 'bg-[var(--badge-amber-bg)] text-[var(--badge-amber-text)] border-[var(--badge-amber-border)]',
    minor: 'bg-[var(--badge-blue-bg)] text-[var(--badge-blue-text)] border-[var(--badge-blue-border)]',
  };
  return (
    <span
      className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-bold uppercase border ${colors[severity]}`}
    >
      {severity}
    </span>
  );
}

export default function Analysis() {
  // ── Restore last analysis (survives TraceView/browser back navigation) ────
  const [lastAnalysis] = useState(getLastAnalysis);

  // ── Shared state ──────────────────────────────────────────────────────────
  const [mode, setMode] = useState<InputMode>(lastAnalysis?.mode ?? 'text');
  const [status, setStatus] = useState<'idle' | 'loading' | 'error'>('idle');
  const [error, setError] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);

  // ── Text-mode state ───────────────────────────────────────────────────────
  const [text, setText] = useState(lastAnalysis?.text ?? '');
  const [result, setResult] = useState<AnalysisResult | null>(lastAnalysis?.result ?? null);
  const [skipCache, setSkipCache] = useState(lastAnalysis?.skipCache ?? true);
  const [fastTrack, setFastTrack] = useState(lastAnalysis?.fastTrack ?? false);
  const abortRef = useRef<AbortController | null>(null);
  const reportDropdownRef = useRef<HTMLDivElement>(null);

  // ── Document-mode state ───────────────────────────────────────────────────
  const [uploadedDoc, setUploadedDoc] = useState<DocumentUploadResponse | null>(
    lastAnalysis?.uploadedDoc ?? null,
  );
  const [docAnalysis, setDocAnalysis] = useState<DocumentAnalysisResult | null>(
    lastAnalysis?.docAnalysis ?? null,
  );
  const [reportDropdownOpen, setReportDropdownOpen] = useState(false);

  // ── Persist current analysis so back-navigation restores it ───────────────
  useEffect(() => {
    saveLastAnalysis({
      mode,
      text,
      result,
      uploadedDoc,
      docAnalysis,
      skipCache,
      fastTrack,
    });
  }, [mode, text, result, uploadedDoc, docAnalysis, skipCache, fastTrack]);

  // ── Click-outside for report dropdown ─────────────────────────────────────
  useEffect(() => {
    if (!reportDropdownOpen) return;
    const handler = (e: MouseEvent) => {
      if (reportDropdownRef.current && !reportDropdownRef.current.contains(e.target as Node)) {
        setReportDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [reportDropdownOpen]);

  // ── Text analysis ─────────────────────────────────────────────────────────
  const handleSubmit = useCallback(async () => {
    const t = text.trim();
    if (t.length < 2) {
      setError('Please enter at least 2 characters to analyze.');
      setStatus('error');
      return;
    }
    if (status === 'loading') return;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setStatus('loading');
    setError(null);
    setResult(null);
    const start = performance.now();
    try {
      const body = {
        text: t,
        include_explanations: true,
        skip_cache: skipCache,
        fast_track: fastTrack,
      };
      const res = await fetch(API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: controller.signal,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `Request failed (${res.status})`);
      }
      const data: AnalysisResult = await res.json();
      validateAnalysisResult(data);
      setResult(data);
      addToHistory(data);
      setStatus('idle');
      setElapsed(performance.now() - start);
    } catch (e: unknown) {
      if (e instanceof Error && e.name === 'AbortError') return;
      setError(e instanceof Error ? e.message : 'Unknown error');
      setStatus('error');
    }
  }, [text, status, skipCache, fastTrack]);

  const handleCancel = useCallback(() => {
    abortRef.current?.abort();
    setStatus('idle');
  }, []);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.ctrlKey && e.key === 'Enter') {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit],
  );

  // ── Document analysis ─────────────────────────────────────────────────────
  const handleDocUploaded = useCallback(async (doc: DocumentUploadResponse) => {
    setUploadedDoc(doc);
    setDocAnalysis(null);
    setError(null);
    setStatus('loading');
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const start = performance.now();
    try {
      const res = await fetch(DOC_ANALYZE_URL(doc.document_id), {
        method: 'POST',
        signal: controller.signal,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `Analysis failed (${res.status})`);
      }
      const data: DocumentAnalysisResult = await res.json();
      validateAnalysisResult(data.overall);
      setDocAnalysis(data);
      addToHistory(data.overall);
      setStatus('idle');
      setElapsed(performance.now() - start);
    } catch (e: unknown) {
      if (e instanceof Error && e.name === 'AbortError') return;
      setError(e instanceof Error ? e.message : 'Document analysis failed');
      setStatus('error');
    }
  }, []);

  const handleUploadError = useCallback((msg: string) => {
    setError(msg);
    setStatus('error');
  }, []);

  const handleDownloadReport = useCallback(
    async (fmt: 'pdf' | 'json') => {
      if (!docAnalysis) return;
      setReportDropdownOpen(false);
      const url = DOC_REPORT_URL(docAnalysis.document.document_id, fmt);
      try {
        const res = await fetch(url);
        if (!res.ok) throw new Error(`Download failed (${res.status})`);
        const blob = await res.blob();
        const blobUrl = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = blobUrl;
        a.download = `report.${fmt}`;
        a.click();
        URL.revokeObjectURL(blobUrl);
      } catch {
        // download failed silently
      }
    },
    [docAnalysis],
  );

  // ── Derived display values ─────────────────────────────────────────────────
  const activeResult = mode === 'text' ? result : docAnalysis?.overall ?? null;
  const logicScore = activeResult?.logic_score ?? 0;
  const scoreTextColor =
    logicScore >= 0.7 ? 'text-app-high' : logicScore >= 0.4 ? 'text-app-med' : 'text-app-low';
  const scoreBarColor =
    logicScore >= 0.7
      ? 'bg-app-high-bar'
      : logicScore >= 0.4
        ? 'bg-app-med-bar'
        : 'bg-app-low-bar';

  const contradictions =
    activeResult?.cross_segment_contradictions?.contradictions ?? [];

  return (
    <main className="min-h-screen bg-app-bg">
      <h1 className="sr-only">Analysis</h1>
      <div className="max-w-7xl mx-auto p-4 sm:p-6 grid grid-cols-1 lg:grid-cols-5 gap-4 sm:gap-6">
        {/* ── Left Panel ───────────────────────────────────────────────────── */}
        <div className="lg:col-span-2 space-y-4">
          <div className="bg-app-card border border-app-border rounded-xl p-4 sm:p-5">
            {/* Mode tabs */}
            <div
              id="analysis-mode-tabs"
              className="flex flex-col sm:flex-row gap-1 mb-4 bg-app-bg rounded-lg p-1 border border-app-border"
              role="tablist"
              aria-label="Input mode"
            >
              {(['text', 'document'] as InputMode[]).map((m) => (
                <button
                  key={m}
                  id={`tab-${m}`}
                  role="tab"
                  aria-selected={mode === m}
                  onClick={() => {
                    setMode(m);
                    setError(null);
                    setResult(null);
                    setDocAnalysis(null);
                    setStatus('idle');
                  }}
                  className={[
                    'flex-1 py-1.5 text-xs font-bold uppercase tracking-wider rounded-md transition-all focus:outline-none focus:ring-2 focus:ring-amber-500',
                    mode === m
                      ? 'bg-amber-600 text-black shadow'
                      : 'text-app-text-muted hover:text-app-text-secondary',
                  ].join(' ')}
                >
                  {m === 'text' ? 'Text' : 'Document'}
                </button>
              ))}
            </div>

            {/* TEXT MODE */}
            {mode === 'text' && (
              <>
                <label
                  htmlFor="input-text"
                  className="block text-xs font-semibold text-app-text-secondary uppercase tracking-wider mb-2"
                >
                  Enter text
                </label>
                <textarea
                  id="input-text"
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Paste a sentence or paragraph here..."
                  rows={8}
                  className="w-full resize-y rounded-lg bg-app-input-bg border border-app-input-border text-app-text p-3 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-amber-500 placeholder:text-app-placeholder transition-shadow"
                />
                <div className="flex gap-2 mt-3">
                  <button
                    onClick={handleSubmit}
                    disabled={status === 'loading'}
                    aria-label="Analyze text"
                    className="flex-1 min-w-0 sm:min-w-[200px] bg-amber-600 hover:bg-amber-500 disabled:opacity-50 disabled:cursor-not-allowed text-black font-bold py-2 px-4 rounded-lg transition-all text-sm uppercase tracking-wider focus:outline-none focus:ring-2 focus:ring-amber-500"
                  >
                    {status === 'loading' ? (
                      <span className="flex items-center justify-center gap-2">
                        <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                        </svg>
                        Scanning...
                      </span>
                    ) : (
                      'Scan'
                    )}
                  </button>
                  {status === 'loading' && (
                    <button
                      onClick={handleCancel}
                      className="bg-app-card-alt hover:bg-app-card-hover text-app-text-secondary font-semibold py-2 px-4 rounded-lg transition-all text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
                    >
                      Cancel
                    </button>
                  )}
                </div>
                <p className="text-[10px] text-app-text-muted font-mono mt-2">
                  Ctrl+Enter to submit
                </p>
                <div className="flex gap-4 mt-2 flex-wrap">
                  <label className="flex items-center gap-1.5 text-xs text-app-text-muted cursor-pointer select-none">
                    <input
                      type="checkbox"
                      checked={skipCache}
                      onChange={(e) => setSkipCache(e.target.checked)}
                      className="rounded border-app-input-border bg-app-input-bg text-amber-500 focus:ring-2 focus:ring-amber-500"
                    />
                    Skip Cache
                  </label>
                  <label className="flex items-center gap-1.5 text-xs text-app-text-muted cursor-pointer select-none">
                    <input
                      type="checkbox"
                      checked={fastTrack}
                      onChange={(e) => setFastTrack(e.target.checked)}
                      className="rounded border-app-input-border bg-app-input-bg text-amber-500 focus:ring-2 focus:ring-amber-500"
                    />
                    Fast Track
                  </label>
                  {fastTrack && (
                    <p className="text-[10px] text-app-text-muted italic ml-5">
                      Fast Track skips LLM explanations; all fallacies are still detected.
                    </p>
                  )}
                </div>
              </>
            )}

            {/* DOCUMENT MODE */}
            {mode === 'document' && (
              <>
                <p className="text-xs font-semibold text-app-text-secondary uppercase tracking-wider mb-3">
                  Upload Document
                </p>
                <FileUpload
                  onUploaded={handleDocUploaded}
                  onError={handleUploadError}
                  disabled={status === 'loading'}
                />
                {uploadedDoc && (
                  <div className="mt-3 bg-app-bg border border-app-border rounded-lg p-3 text-xs">
                    <p className="font-semibold text-app-text">{uploadedDoc.filename}</p>
                    <p className="text-app-text-muted mt-0.5">
                      {uploadedDoc.page_count} pages · {uploadedDoc.char_count.toLocaleString()} chars
                    </p>
                  </div>
                )}
              </>
            )}
          </div>

          {/* Results summary card */}
          {activeResult && (
            <div className="bg-app-card border border-app-border rounded-xl p-4 sm:p-5" role="region" aria-label="Results summary">
              <h2 className="text-xs font-semibold text-app-text-secondary uppercase tracking-wider mb-4">
                Results
              </h2>
              <div className="grid grid-cols-2 gap-3 mb-4">
                <div className="bg-app-bg rounded-lg border border-app-border p-3">
                  <div className="text-[10px] text-app-text-muted uppercase tracking-wider">Logic Score</div>
                  <div className={`text-lg font-bold font-mono ${scoreTextColor}`}>
                    {Math.round(logicScore * 100)}%
                  </div>
                </div>
                <div className="bg-app-bg rounded-lg border border-app-border p-3">
                  <div className="text-[10px] text-app-text-muted uppercase tracking-wider">Salience</div>
                  <div className="text-lg font-bold font-mono text-app-text">
                    {activeResult.salience_score != null
                      ? activeResult.salience_score.toFixed(2)
                      : '-'}
                  </div>
                </div>
                <div className="bg-app-bg rounded-lg border border-app-border p-3">
                  <div className="text-[10px] text-app-text-muted uppercase tracking-wider">Latency</div>
                  <div className="text-lg font-bold font-mono text-app-text">
                    {activeResult.total_latency_ms >= 1000
                      ? `${(activeResult.total_latency_ms / 1000).toFixed(1)}s`
                      : `${activeResult.total_latency_ms.toFixed(0)}ms`}
                  </div>
                </div>
                <div className="bg-app-bg rounded-lg border border-app-border p-3">
                  <div className="text-[10px] text-app-text-muted uppercase tracking-wider">Fallacies</div>
                  <div className="text-lg font-bold font-mono text-app-text">
                    {activeResult.fallacies.length}
                  </div>
                </div>
              </div>

              <div className="mb-2">
                <div className="flex justify-between text-xs text-app-text-muted mb-1">
                  <span>Logic Score</span>
                  <span>{Math.round(logicScore * 100)}%</span>
                </div>
                <div className="h-2 bg-app-bg rounded-full overflow-hidden border border-app-border">
                  <div
                    className={`h-full rounded-full transition-all duration-700 ease-out ${scoreBarColor}`}
                    style={{ width: `${logicScore * 100}%` }}
                  />
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[10px] text-app-text-muted font-mono mt-3">
                <span>
                  {activeResult.cached
                    ? 'Cached result'
                    : `Completed in ${(elapsed / 1000).toFixed(1)}s`}
                  {activeResult.z3_status && ` · Z3: ${activeResult.z3_status}`}
                </span>
                {activeResult.degradation_tier > 0 && (
                  <span
                    title={`Tier ${activeResult.degradation_tier}: 1=ONNX-CPU+LLM 4-bit, 2=ONNX-CPU+API fallback, 3=ONNX-CPU+rule-based synthesis`}
                    className="inline-flex items-center gap-1 rounded-full border border-amber-500/40 bg-amber-500/10 px-2 py-0.5 text-amber-400"
                  >
                    degraded (tier {activeResult.degradation_tier})
                  </span>
                )}
              </div>

              {/* Download report button — document mode only */}
              {mode === 'document' && docAnalysis && (
                <div className="relative mt-4" id="download-report-container" ref={reportDropdownRef}>
                  <button
                    id="download-report-btn"
                    onClick={() => setReportDropdownOpen((o) => !o)}
                    aria-haspopup="true"
                    aria-expanded={reportDropdownOpen}
                    className="w-full flex items-center justify-center gap-2 bg-app-card-alt hover:bg-app-card-hover border border-app-border text-app-text-secondary font-semibold py-2 px-4 rounded-lg text-xs transition-all focus:outline-none focus:ring-2 focus:ring-amber-500"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                    </svg>
                    Download Report
                    <svg className={`w-3 h-3 transition-transform ${reportDropdownOpen ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </button>
                  {reportDropdownOpen && (
                    <div className="absolute bottom-full mb-1 left-0 right-0 bg-app-card border border-app-border rounded-lg overflow-hidden shadow-xl z-10">
                      <button
                        id="download-pdf-btn"
                        onClick={() => handleDownloadReport('pdf')}
                        className="w-full text-left px-4 py-2.5 text-xs text-app-text hover:bg-app-card-alt transition-colors flex items-center gap-2 focus:outline-none focus:ring-2 focus:ring-amber-500"
                      >
                        PDF Report
                      </button>
                      <button
                        id="download-json-btn"
                        onClick={() => handleDownloadReport('json')}
                        className="w-full text-left px-4 py-2.5 text-xs text-app-text hover:bg-app-card-alt transition-colors flex items-center gap-2 focus:outline-none focus:ring-2 focus:ring-amber-500"
                      >
                        JSON Report
                      </button>
                    </div>
                  )}
                </div>
              )}

              <details className="group mt-4">
                <summary className="text-xs text-app-text-muted cursor-pointer hover:text-app-text-secondary transition-colors list-none flex items-center gap-1 select-none focus:outline-none focus:ring-2 focus:ring-amber-500 rounded">
                  <svg className="w-3 h-3 transition-transform group-open:rotate-90" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                  Pipeline Metadata
                </summary>
                <div className="mt-2 space-y-1 text-xs font-mono text-app-text-muted">
                  {Object.entries(activeResult.stage_latencies ?? {}).map(([stage, lat]) => (
                    <div key={stage} className="flex justify-between py-0.5">
                      <span>{stage}</span>
                      <span>{lat.toFixed(1)}ms</span>
                    </div>
                  ))}
                </div>
              </details>
            </div>
          )}

          {status === 'error' && error && (
            <div className="bg-[var(--badge-red-bg)] border border-[var(--badge-red-border)] text-[var(--badge-red-text)] rounded-xl p-4 text-sm" role="alert">
              {error}
            </div>
          )}
        </div>

        {/* ── Right Panel ───────────────────────────────────────────────────── */}
        <div className="lg:col-span-3 space-y-4 sm:space-y-6 overflow-x-hidden">
          {status === 'loading' && (
            <div className="animate-pulse space-y-6" aria-live="polite" aria-label="Loading analysis results">
              <div className="bg-app-card border border-app-border rounded-xl p-4 sm:p-5">
                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-app-card-alt rounded-lg p-3">
                    <div className="h-3 bg-app-card rounded w-16 mb-2" />
                    <div className="h-6 bg-app-card rounded w-20" />
                  </div>
                  <div className="bg-app-card-alt rounded-lg p-3">
                    <div className="h-3 bg-app-card rounded w-12 mb-2" />
                    <div className="h-6 bg-app-card rounded w-16" />
                  </div>
                </div>
                <div className="mt-4">
                  <div className="h-2 bg-app-card-alt rounded-full w-full" />
                </div>
              </div>
              <div className="space-y-2">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="bg-app-card border border-app-border rounded-lg p-4">
                    <div className="h-4 bg-app-card-alt rounded w-1/3 mb-2" />
                    <div className="h-3 bg-app-card-alt rounded w-2/3 mb-2" />
                    <div className="h-3 bg-app-card-alt rounded w-1/2" />
                  </div>
                ))}
              </div>
              <div className="bg-app-card border border-app-border rounded-xl p-6">
                <div className="space-y-2">
                  {[1, 2, 3, 4].map((i) => (
                    <div key={i} className="h-3 bg-app-card-alt rounded w-full" />
                  ))}
                </div>
              </div>
              <p className="text-sm text-app-text-muted text-center">
                {mode === 'document' ? 'Analyzing document…' : 'Running pipeline…'}
              </p>
            </div>
          )}

          {activeResult && (
            <div className="space-y-4 sm:space-y-6" role="region" aria-label="Analysis results">
              {/* Per-page results (document mode only) */}
              {mode === 'document' && docAnalysis && docAnalysis.per_page.length > 0 && (
                <PerPageResults pages={docAnalysis.per_page} />
              )}

              {/* Annotated full text */}
              <AnnotatedText
                text={activeResult.input_text}
                annotations={activeResult.annotations}
                salientTokens={activeResult.salient_tokens}
              />

              {/* Fallacy cards */}
              {activeResult.fallacies.length > 0 && (
                <div>
                  <h3 className="text-xs font-semibold text-app-text-secondary uppercase tracking-wider mb-3">
                    Detected Fallacies ({activeResult.fallacies.length})
                  </h3>
                  <div className="space-y-1">
                    {activeResult.fallacies.map((f, i) => (
                      <div
                        key={`${f.name}-${i}`}
                        className="animate-fadeIn"
                        style={{ animationDelay: `${i * 50}ms` }}
                      >
                        <FallacyCard fallacy={f} analysisId={activeResult.analysis_id} />
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {activeResult.fallacies.length === 0 && activeResult.coarse_category && (
                <div className="p-4 text-center text-app-text-muted">
                  No logical fallacies detected.
                </div>
              )}

              {/* Cross-segment contradictions */}
              <div id="cross-segment-contradictions-section">
                <h3 className="text-xs font-semibold text-app-text-secondary uppercase tracking-wider mb-3">
                  Cross-Segment Contradictions
                  {contradictions.length > 0 && (
                    <span className="ml-2 inline-block px-1.5 py-0.5 bg-[var(--badge-red-bg)] text-[var(--badge-red-text)] border border-[var(--badge-red-border)] rounded text-[9px] font-bold">
                      {contradictions.length}
                    </span>
                  )}
                </h3>
                {contradictions.length > 0 ? (
                  <div className="space-y-2">
                    {contradictions.map((c, i) => (
                      <div
                        key={i}
                        id={`contradiction-${i}`}
                        className="bg-app-card border border-app-border rounded-lg p-3 animate-fadeIn"
                        style={{
                          borderLeft: `3px solid ${
                            c.severity === 'critical'
                              ? '#ef4444'
                              : c.severity === 'moderate'
                                ? '#f59e0b'
                                : '#3b82f6'
                          }`,
                        }}
                      >
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-xs font-bold text-app-text-secondary">
                            {c.segment_a_page && c.segment_b_page
                              ? `Page ${c.segment_a_page} ↔ Page ${c.segment_b_page}`
                              : `Segment ${c.segment_a_index + 1} ↔ Segment ${c.segment_b_index + 1}`}
                          </span>
                          <div className="flex items-center gap-1.5">
                            <SeverityBadge severity={c.severity} />
                            <span className="text-[10px] font-mono text-app-text-muted">
                              {c.type} · {Math.round(c.confidence * 100)}%
                            </span>
                          </div>
                        </div>
                        <p className="text-xs text-app-text-muted">{c.description}</p>
                        {/* Scroll-to-page links */}
                        {c.segment_a_page && c.segment_b_page && (
                          <div className="flex gap-2 mt-1.5">
                            {[c.segment_a_page, c.segment_b_page].map((pg) => (
                              <button
                                key={pg}
                                onClick={() => {
                                  document
                                    .getElementById(`page-result-${pg}`)
                                    ?.scrollIntoView({ behavior: 'smooth' });
                                  document
                                    .getElementById(`page-result-${pg}`)
                                    ?.click();
                                }}
                                className="text-[10px] text-amber-400 hover:text-amber-300 underline transition-colors focus:outline-none focus:ring-2 focus:ring-amber-500 rounded"
                              >
                                ↗ View Page {pg}
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                ) : activeResult ? (
                  <p className="text-xs text-app-text-muted italic">
                    No cross-segment contradictions detected.
                  </p>
                ) : null}
              </div>

              {/* Correction strategy */}
              {activeResult.correction_strategy && (
                <div className="bg-[var(--badge-green-bg)] border border-[var(--badge-green-border)] rounded-xl p-4">
                  <h4 className="text-xs font-semibold text-[var(--badge-green-text)] uppercase tracking-wider mb-1">
                    Correction
                  </h4>
                  <p className="text-sm text-[var(--badge-green-text)]">{activeResult.correction_strategy}</p>
                </div>
              )}
            </div>
          )}

          {status === 'idle' && !activeResult && (
            <div className="bg-app-card border border-app-border rounded-xl p-10 text-center" role="region" aria-label="Welcome message">
              <p className="text-app-text-muted">
                <span className="text-amber-500/70">&gt;</span>{' '}
                {mode === 'text' ? (
                  <>
                    Enter text and press{' '}
                    <span className="text-amber-500">Scan</span> to detect logical fallacies.
                  </>
                ) : (
                  <>
                    Upload a <span className="text-amber-500">PDF, DOCX, or TXT</span> file to
                    analyze it for logical fallacies.
                  </>
                )}
              </p>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
