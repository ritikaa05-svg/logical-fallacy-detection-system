import { useEffect, useState, useRef, useCallback } from 'react';
import { ApiResponseError } from '../lib/validation';
import type { ChatMessage, DebateResponse } from '../types/api';

interface Props {
  open: boolean;
  onClose: () => void;
}

const ACTION_COLORS: Record<string, string> = {
  ASK_SOCRATIC: 'bg-[var(--badge-purple-bg)] text-[var(--badge-purple-text)] border-[var(--badge-purple-border)]',
  POINT_OUT_FALLACY: 'bg-[var(--badge-red-bg)] text-[var(--badge-red-text)] border-[var(--badge-red-border)]',
  COUNTER_ARGUMENT: 'bg-[var(--badge-blue-bg)] text-[var(--badge-blue-text)] border-[var(--badge-blue-border)]',
  AGREE_AND_PIVOT: 'bg-[var(--badge-green-bg)] text-[var(--badge-green-text)] border-[var(--badge-green-border)]',
};

function TypingIndicator() {
  const [dots, setDots] = useState('');
  useEffect(() => {
    const interval = setInterval(() => {
      setDots(prev => prev.length >= 3 ? '' : prev + '.');
    }, 400);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex items-center gap-1.5">
      <span className="text-sm text-app-text-muted">Thinking{dots}</span>
    </div>
  );
}

export default function DebateDrawer({ open, onClose }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([{
    role: 'assistant',
    content: 'Start a debate. Present an argument and I will analyze its logical structure, point out fallacies, and challenge your reasoning.',
  }]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const mountedRef = useRef(true);
  const prevMessageCount = useRef(1);

  const handleEscape = useCallback((e: KeyboardEvent) => {
    if (e.key === 'Escape' && open && !sending) {
      onClose();
    }
  }, [open, sending, onClose]);

  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  useEffect(() => {
    if (open) {
      document.addEventListener('keydown', handleEscape);
      return () => document.removeEventListener('keydown', handleEscape);
    }
  }, [open, handleEscape]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    if (open && !sending) {
      setTimeout(() => inputRef.current?.focus(), 300);
    }
  }, [open, sending]);

  const send = async () => {
    const text = inputRef.current?.value ?? '';
    if (!text.trim() || sending) return;
    inputRef.current!.value = '';

    const userMsg: ChatMessage = { role: 'user', content: text };
    const placeholder: ChatMessage = {
      role: 'assistant',
      content: '',
      isStreaming: true,
    };

    prevMessageCount.current = messages.length;
    setMessages(prev => [...prev, userMsg, placeholder]);
    setSending(true);

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    const startTime = performance.now();

    try {
      const res = await fetch('/api/v1/debate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, user_input: text }),
        signal: controller.signal,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || 'Debate request failed');
      }

      const data: DebateResponse = await res.json();
      if (!data || typeof data !== 'object' || !data.session_id) {
        throw new ApiResponseError('Invalid debate response from server');
      }
      if (!mountedRef.current) return;
      setSessionId(data.session_id);

      const elapsed = performance.now() - startTime;
      const remaining = Math.max(0, 400 - elapsed);
      await new Promise(r => setTimeout(r, remaining));

      if (!mountedRef.current) return;
      setMessages(prev =>
        prev.map(m =>
          m.isStreaming
            ? {
                role: 'assistant' as const,
                content: data.agent_response,
                action: data.agent_action,
                logic_score: data.logic_score,
                fallacies: data.detected_fallacies,
                isStreaming: false,
              }
            : m,
        ),
      );
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') return;
      if (!mountedRef.current) return;
      const msg = err instanceof Error ? err.message : 'Unknown error';
      setMessages(prev =>
        prev.map(m =>
          m.isStreaming
            ? { role: 'assistant' as const, content: `Error: ${msg}` }
            : m,
        ),
      );
    } finally {
      if (mountedRef.current) setSending(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    send();
  };

  const clearChat = () => {
    setMessages([{
      role: 'assistant',
      content: 'Start a debate. Present an argument and I will analyze its logical structure, point out fallacies, and challenge your reasoning.',
    }]);
    setSessionId(null);
  };

  return (
    <>
      {open && (
        <div
          className="fixed inset-0 z-40 bg-black/60 animate-fadeInBackdrop"
          onClick={onClose}
        />
      )}

      <div className={`
        fixed top-0 right-0 z-50 h-full w-full max-w-lg bg-app-card
        border-l border-app-border shadow-2xl
        flex flex-col transition-transform duration-300 ease-out
        ${open ? 'translate-x-0' : 'translate-x-full'}
      `}>
        <div className="flex items-center justify-between px-4 sm:px-5 py-3 border-b border-app-border">
          <h2 className="text-sm font-bold text-app-text uppercase tracking-wider">
            Debate
          </h2>
          <div className="flex items-center gap-3">
            <button
              onClick={clearChat}
              className="text-xs text-app-text-muted hover:text-app-text-secondary transition-colors"
            >
              Clear
            </button>
            <button
              onClick={onClose}
              className="text-sm text-app-text-muted hover:text-app-text-secondary transition-colors"
              aria-label="Close debate"
            >
              &times;
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-4 sm:px-5 py-4 space-y-4">
          {messages.map((m, i) => (
            <div
              key={i}
              className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'} ${i >= prevMessageCount.current ? 'animate-fadeIn' : ''}`}
              style={i >= prevMessageCount.current ? { animationDelay: `${(i - prevMessageCount.current) * 30}ms` } : undefined}
            >
              <div
                className={`max-w-[85%] rounded-xl px-4 py-3 ${
                  m.role === 'user'
                    ? 'bg-amber-600 text-black rounded-br-sm'
                    : 'bg-app-bg border border-app-border text-app-text rounded-bl-sm'
                }`}
              >
                {m.role === 'assistant' && !m.isStreaming && m.action && (
                  <div className="mb-2">
                    <span className={`inline-block text-[10px] font-semibold px-2 py-0.5 rounded border ${ACTION_COLORS[m.action] || 'bg-app-card-alt text-app-text-muted border-app-border'}`}>
                      {m.action.replace(/_/g, ' ')}
                    </span>
                  </div>
                )}
                {m.isStreaming ? (
                  <TypingIndicator />
                ) : (
                  <p className="text-sm whitespace-pre-wrap leading-relaxed">{m.content}</p>
                )}
                {m.role === 'assistant' && !m.isStreaming && m.logic_score !== undefined && (
                  <div className="mt-2 flex items-center gap-2 text-[10px] text-app-text-muted font-mono border-t border-app-border pt-2">
                    <span>Score: {Math.round(m.logic_score * 100)}%</span>
                    {m.fallacies && m.fallacies.length > 0 && (
                      <span>{m.fallacies.length} fallac{m.fallacies.length === 1 ? 'y' : 'ies'}</span>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>

        <form onSubmit={handleSubmit} className="border-t border-app-border p-4">
          <div className="flex gap-2">
            <input
              ref={inputRef}
              placeholder="Present your argument..."
              disabled={sending}
              className="flex-1 rounded-lg bg-app-input-bg border border-app-input-border text-app-text px-4 py-2.5 text-sm focus:outline-none focus:ring-1 focus:ring-amber-500 focus:border-amber-500 placeholder:text-app-placeholder disabled:opacity-50 transition-shadow"
            />
            <button
              type="submit"
              disabled={sending}
              className="bg-amber-600 hover:bg-amber-500 disabled:opacity-50 disabled:cursor-not-allowed text-black font-bold px-5 py-2.5 rounded-lg transition-all text-sm uppercase tracking-wider shrink-0"
            >
              Send
            </button>
          </div>
        </form>
      </div>
    </>
  );
}
