import React, { useState } from 'react';
import { Lightbulb, X } from 'lucide-react';

const KEY = 'clubdocs.editor-tips.v1';

function seen(): boolean {
  try {
    return window.localStorage.getItem(KEY) === 'done';
  } catch {
    return true;
  }
}

/** The editor's handful of shortcuts, shown once to first-time users; dismiss to hide for good. */
export const EditorTips: React.FC = () => {
  const [open, setOpen] = useState(() => !seen());
  if (!open) return null;

  const close = () => {
    try {
      window.localStorage.setItem(KEY, 'done');
    } catch {
      /* ignore */
    }
    setOpen(false);
  };

  const kbd = 'rounded border border-slate-300 bg-white px-1 py-px font-mono text-[11px] text-slate-700';
  return (
    <div role="note" className="fixed bottom-4 left-1/2 z-40 w-[min(40rem,calc(100vw-2rem))] -translate-x-1/2 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 shadow-lg">
      <div className="flex items-start gap-3">
        <Lightbulb className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
        <div className="flex-1 text-xs leading-relaxed text-slate-700">
          <p className="font-semibold text-slate-900">Quick tips</p>
          <p className="mt-1">
            Type <kbd className={kbd}>{'{{'}</kbd> to add a field (a part that changes per document), <kbd className={kbd}>/</kbd> for
            blocks like tables and signatures, and right-click for formatting. <kbd className={kbd}>Ctrl+P</kbd> previews with sample
            data and <kbd className={kbd}>Ctrl+S</kbd> saves (it also saves by itself).
          </p>
        </div>
        <button type="button" onClick={close} className="rounded p-1 text-slate-500 hover:bg-amber-100 hover:text-slate-800" aria-label="Got it, hide tips">
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
};
