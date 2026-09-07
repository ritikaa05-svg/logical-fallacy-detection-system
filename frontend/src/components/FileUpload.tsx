import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiResponseError } from '../lib/validation';
import type { DocumentUploadResponse } from '../types/api';

interface Props {
  onUploaded: (doc: DocumentUploadResponse) => void;
  onError: (msg: string) => void;
  disabled?: boolean;
}

const ACCEPTED_TYPES = ['.pdf', '.docx', '.txt'];
const MAX_MB = 20;

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1_048_576) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1_048_576).toFixed(1)} MB`;
}

export default function FileUpload({ onUploaded, onError, disabled = false }: Props) {
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const mountedRef = useRef(true);

  const validateFile = useCallback((file: File): string | null => {
    const ext = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!ACCEPTED_TYPES.includes(ext)) {
      return `Unsupported format "${ext}". Allowed: ${ACCEPTED_TYPES.join(', ')}`;
    }
    if (file.size > MAX_MB * 1_048_576) {
      return `File too large (${formatBytes(file.size)}). Maximum: ${MAX_MB} MB`;
    }
    return null;
  }, []);

  const handleFileSelect = useCallback(
    (file: File) => {
      const err = validateFile(file);
      if (err) {
        onError(err);
        return;
      }
      setSelectedFile(file);
      setProgress(0);
    },
    [validateFile, onError],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFileSelect(file);
    },
    [handleFileSelect],
  );

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleFileSelect(file);
      // Reset input so same file can be re-selected
      e.target.value = '';
    },
    [handleFileSelect],
  );

  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  const handleUpload = useCallback(async () => {
    if (!selectedFile || uploading || disabled) return;

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setUploading(true);
    setProgress(10);

    const formData = new FormData();
    formData.append('file', selectedFile);

    const progressInterval = setInterval(() => {
      setProgress((p) => Math.min(p + 15, 85));
    }, 300);

    try {
      const res = await fetch('/api/v1/documents/upload', {
        method: 'POST',
        body: formData,
        signal: controller.signal,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `Upload failed (${res.status})`);
      }

      setProgress(100);

      const data: DocumentUploadResponse = await res.json();
      if (!data || typeof data !== 'object' || !data.document_id) {
        throw new ApiResponseError('Invalid upload response from server');
      }
      if (mountedRef.current) onUploaded(data);
    } catch (e: unknown) {
      if (e instanceof Error && e.name === 'AbortError') return;
      const msg = e instanceof Error ? e.message : 'Upload failed';
      if (mountedRef.current) onError(msg);
    } finally {
      clearInterval(progressInterval);
      if (mountedRef.current) setUploading(false);
    }
  }, [selectedFile, uploading, disabled, onUploaded, onError]);

  return (
    <div className="space-y-3">
      {/* Drop Zone */}
      <div
        id="file-upload-dropzone"
        role="button"
        tabIndex={0}
        aria-label="File upload drop zone"
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => {
          if (disabled) return;
          if (e.key === 'Enter' || e.key === ' ') inputRef.current?.click();
        }}
        className={[
          'relative flex flex-col items-center justify-center gap-2 w-full',
          'rounded-xl border-2 border-dashed p-8 cursor-pointer',
          'transition-all duration-200 select-none',
          'focus:outline-none focus:ring-2 focus:ring-amber-500',
          isDragging
            ? 'border-amber-500 bg-amber-500/10 scale-[1.01]'
            : 'border-app-border bg-app-input-bg hover:border-amber-500/60 hover:bg-amber-500/5',
          disabled ? 'opacity-50 pointer-events-none' : '',
        ].join(' ')}
      >
        {/* Cloud Upload Icon */}
        <svg
          className={`w-10 h-10 transition-colors ${isDragging ? 'text-amber-400' : 'text-app-text-muted'}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
          />
        </svg>

        <div className="text-center">
          <p className="text-sm font-semibold text-app-text-secondary">
            {isDragging ? 'Drop to upload' : 'Drag & drop or click to browse'}
          </p>
          <p className="text-xs text-app-text-muted mt-1">
            PDF, DOCX, TXT &mdash; max {MAX_MB} MB
          </p>
        </div>

        <input
          ref={inputRef}
          id="file-upload-input"
          type="file"
          accept={ACCEPTED_TYPES.join(',')}
          onChange={handleInputChange}
          className="sr-only"
          aria-hidden="true"
        />
      </div>

      {/* Selected file info */}
      {selectedFile && (
        <div className="flex items-center gap-3 bg-app-card border border-app-border rounded-lg px-3 py-2">
          {/* File type icon */}
          <div className="flex-shrink-0 w-8 h-8 rounded-md bg-amber-500/20 flex items-center justify-center">
            <svg className="w-4 h-4 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-semibold text-app-text truncate">{selectedFile.name}</p>
            <p className="text-xs text-app-text-muted">{formatBytes(selectedFile.size)}</p>
          </div>
          <button
            onClick={(e) => {
              e.stopPropagation();
              setSelectedFile(null);
              setProgress(0);
            }}
            className="text-app-text-muted hover:text-red-400 transition-colors p-1"
            aria-label="Remove selected file"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      )}

      {/* Progress bar */}
      {uploading && (
        <div className="space-y-1">
          <div className="flex justify-between text-xs text-app-text-muted">
            <span>Uploading & parsing…</span>
            <span>{progress}%</span>
          </div>
          <div className="h-1.5 bg-app-bg rounded-full overflow-hidden border border-app-border">
            <div
              className="h-full bg-amber-500 rounded-full transition-all duration-300 ease-out"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      )}

      {/* Upload button */}
      <button
        id="file-upload-submit"
        onClick={handleUpload}
        disabled={!selectedFile || uploading || disabled}
        className="w-full sm:w-auto bg-amber-600 hover:bg-amber-500 disabled:opacity-40 disabled:cursor-not-allowed text-black font-bold py-2 px-4 rounded-lg transition-all text-sm uppercase tracking-wider flex items-center justify-center gap-2"
      >
        {uploading ? (
          <>
            <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Uploading…
          </>
        ) : (
          <>
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
            </svg>
            Upload &amp; Analyze
          </>
        )}
      </button>
    </div>
  );
}
