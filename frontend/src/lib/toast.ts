const bus = new EventTarget();

export interface ToastEvent {
  message: string;
  type: 'error' | 'info';
}

export function showToast(message: string, type: ToastEvent['type'] = 'error') {
  bus.dispatchEvent(new CustomEvent<ToastEvent>('toast', { detail: { message, type } }));
}

export function onToast(cb: (e: ToastEvent) => void) {
  const handler = (event: Event) => {
    cb((event as CustomEvent<ToastEvent>).detail);
  };
  bus.addEventListener('toast', handler);
  return () => bus.removeEventListener('toast', handler);
}
