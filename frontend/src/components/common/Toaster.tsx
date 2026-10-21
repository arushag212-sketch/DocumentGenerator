import React, { useEffect, useState } from 'react';
import { CheckCircle2, AlertCircle, Info, X } from 'lucide-react';

type Tone = 'success' | 'error' | 'info';
type Toast = { id: number; text: string; tone: Tone };

const EVENT = 'clubdocs-app-toast';

/** Show a short message in the corner of the app (use instead of alert()). */
export function notify(text: string, tone: Tone = 'info') {
  window.dispatchEvent(new CustomEvent(EVENT, { detail: { text, tone } }));
}

const STYLE: Record<Tone, { icon: React.ElementType; className: string }> = {
  success: { icon: CheckCircle2, className: 'border-emerald-200 text-emerald-800' },
  error: { icon: AlertCircle, className: 'border-red-200 text-red-700' },
  info: { icon: Info, className: 'border-slate-200 text-slate-700' },
};

export const Toaster: React.FC = () => {
  const [toasts, setToasts] = useState<Toast[]>([]);

  useEffect(() => {
    let next = 1;
    const onToast = (e: Event) => {
      const { text, tone } = (e as CustomEvent<{ text: string; tone: Tone }>).detail;
      const id = next++;
      setToasts((t) => [...t.slice(-2), { id, text, tone }]);
      window.setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), tone === 'error' ? 7000 : 4000);
    };
    window.addEventListener(EVENT, onToast);
    return () => window.removeEventListener(EVENT, onToast);
  }, []);

  return (
    <div className="fixed bottom-4 right-4 z-[90] flex w-[min(24rem,calc(100vw-2rem))] flex-col gap-2" aria-live="polite">
      {toasts.map(({ id, text, tone }) => {
        const { icon: Icon, className } = STYLE[tone];
        return (
          <div key={id} role={tone === 'error' ? 'alert' : 'status'} className={`flex items-start gap-2.5 rounded-lg border bg-white px-3.5 py-3 text-sm shadow-lg ${className}`}>
            <Icon className="mt-0.5 h-4 w-4 shrink-0" />
            <span className="flex-1">{text}</span>
            <button
              type="button"
              onClick={() => setToasts((t) => t.filter((x) => x.id !== id))}
              className="rounded p-0.5 text-slate-400 hover:text-slate-700"
              aria-label="Dismiss"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        );
      })}
    </div>
  );
};
