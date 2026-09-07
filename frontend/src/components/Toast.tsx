import { useEffect, useState, useCallback, useRef } from 'react';
import { onToast, type ToastEvent } from '../lib/toast';

interface Item {
  id: number;
  message: string;
  type: 'error' | 'info';
}

let nextId = 0;
const MAX_VISIBLE = 5;

export default function Toast() {
  const [items, setItems] = useState<Item[]>([]);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const remove = useCallback((id: number) => {
    setItems(prev => prev.filter(i => i.id !== id));
  }, []);

  useEffect(() => {
    return onToast((e: ToastEvent) => {
      const id = nextId++;
      setItems(prev => {
        const next = [...prev, { id, message: e.message, type: e.type }];
        return next.length > MAX_VISIBLE ? next.slice(next.length - MAX_VISIBLE) : next;
      });
      timeoutRef.current = setTimeout(() => remove(id), 5000);
    });
  }, [remove]);

  useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, []);

  if (items.length === 0) return null;

  return (
    <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-[60] flex flex-col gap-2 max-w-md w-full px-4">
      {items.map(item => (
        <div
          key={item.id}
          role="alert"
          aria-live="assertive"
          className={`flex items-center gap-3 px-4 py-3 rounded-xl shadow-lg text-sm font-mono animate-slideUp ${
            item.type === 'error'
              ? 'bg-[var(--badge-red-bg)] border border-[var(--badge-red-border)] text-[var(--badge-red-text)]'
              : 'bg-app-card border border-app-border text-app-text'
          }`}
        >
          <span className="flex-1">{item.message}</span>
          <button
            onClick={() => remove(item.id)}
            className="text-xs opacity-60 hover:opacity-100 transition-opacity"
          >
            &times;
          </button>
        </div>
      ))}
    </div>
  );
}
