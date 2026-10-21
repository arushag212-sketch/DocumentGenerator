import React, { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Lock, Trash2, X, AlertCircle } from 'lucide-react';

interface ChipPopoverProps {
  chipPopover: any;
  onClose: () => void;
  onUpdateChip: (updates: any) => void;
  onToggleRequired: (req: boolean) => void;
  onToggleSensitive: (sens: boolean) => void;
  onDelete: () => void;
}

export const ChipPopover: React.FC<ChipPopoverProps> = ({
  chipPopover,
  onClose,
  onUpdateChip,
  onToggleRequired,
  onToggleSensitive,
  onDelete,
}) => {
  const popoverRef = useRef<HTMLDivElement>(null);
  const [stylePos, setStylePos] = useState({ top: chipPopover?.top ?? 100, left: chipPopover?.left ?? 100 });
  const [confirmDelete, setConfirmDelete] = useState(false);

  // Keep popover fully on screen
  useLayoutEffect(() => {
    if (!chipPopover || !popoverRef.current) return;
    const rect = popoverRef.current.getBoundingClientRect();
    const margin = 12;
    const maxLeft = Math.max(margin, window.innerWidth - rect.width - margin);
    const maxTop = Math.max(margin, window.innerHeight - rect.height - margin);

    const clampedLeft = Math.max(margin, Math.min(chipPopover.left, maxLeft));
    const clampedTop = Math.max(margin, Math.min(chipPopover.top, maxTop));

    setStylePos({ top: clampedTop, left: clampedLeft });
  }, [chipPopover?.top, chipPopover?.left]);

  // Close on Escape or click outside
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    const handleClickOutside = (e: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        onClose();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    // Slight timeout so click that opened popover does not immediately close it
    const timer = setTimeout(() => {
      window.addEventListener('mousedown', handleClickOutside);
    }, 50);

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('mousedown', handleClickOutside);
      clearTimeout(timer);
    };
  }, [onClose]);

  if (!chipPopover) return null;

  return (
    <div
      ref={popoverRef}
      style={{ top: `${stylePos.top}px`, left: `${stylePos.left}px` }}
      className="fixed z-50 bg-white border border-slate-200 rounded-xl shadow-2xl p-4 w-80 text-xs space-y-3.5 animate-in fade-in zoom-in-95 duration-100"
      role="dialog"
      aria-label="Edit Field Chip"
    >
      <div className="flex items-center justify-between pb-2 border-b border-slate-100">
        <div className="flex items-center gap-1.5 min-w-0">
          <span className="font-bold text-slate-800 text-xs truncate">
            {chipPopover.label || chipPopover.fieldName}
          </span>
          <span className="text-[10px] font-mono px-1 py-0.5 rounded bg-slate-100 text-slate-500 shrink-0">
            {`{{ ${chipPopover.fieldName} }}`}
          </span>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition"
          aria-label="Close"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>

      <div>
        <label className="block text-xs font-semibold text-slate-700 mb-1">
          Human Label
        </label>
        <input
          type="text"
          value={chipPopover.label || ''}
          onChange={(e) => onUpdateChip({ label: e.target.value })}
          placeholder="e.g. Event Name"
          className="w-full px-2.5 py-1.5 border border-slate-300 rounded-lg text-xs focus:ring-1 focus:ring-brand-500 focus:outline-none bg-slate-50 focus:bg-white"
        />
        <p className="text-[11px] text-slate-500 mt-0.5">Displayed on canvas and form prompts.</p>
      </div>

      <div className="grid grid-cols-2 gap-2 pt-1">
        <div className="p-2 rounded-lg border border-slate-200 bg-slate-50/50 flex flex-col justify-between">
          <span className="text-[11px] font-semibold text-slate-600">Requirement</span>
          <button
            type="button"
            onClick={() => onToggleRequired(!chipPopover.required)}
            className={`mt-1.5 w-full py-1 px-2 rounded text-xs font-semibold transition ${
              chipPopover.required
                ? 'bg-rose-100 text-rose-800 border border-rose-300 shadow-xs'
                : 'bg-white text-slate-600 border border-slate-200 hover:border-slate-300'
            }`}
          >
            {chipPopover.required ? '★ Required' : 'Optional'}
          </button>
        </div>

        <div className="p-2 rounded-lg border border-slate-200 bg-slate-50/50 flex flex-col justify-between">
          <span className="text-[11px] font-semibold text-slate-600">Sensitive Data</span>
          <button
            type="button"
            onClick={() => onToggleSensitive(!chipPopover.sensitive)}
            className={`mt-1.5 w-full py-1 px-2 rounded text-xs font-semibold transition flex items-center justify-center gap-1 ${
              chipPopover.sensitive
                ? 'bg-amber-100 text-amber-800 border border-amber-300 shadow-xs'
                : 'bg-white text-slate-600 border border-slate-200 hover:border-slate-300'
            }`}
          >
            <Lock className="w-3 h-3" />
            <span>{chipPopover.sensitive ? 'Protected' : 'Standard'}</span>
          </button>
        </div>
      </div>

      <div className="pt-2 border-t border-slate-100 flex justify-between items-center">
        {confirmDelete ? (
          <div className="flex items-center gap-1.5 animate-in fade-in">
            <span className="text-[11px] text-rose-700 font-semibold flex items-center gap-0.5">
              <AlertCircle className="w-3 h-3 text-rose-600" /> Remove?
            </span>
            <button
              type="button"
              onClick={onDelete}
              className="px-2 py-0.5 bg-rose-600 text-white rounded text-xs font-semibold hover:bg-rose-700"
            >
              Yes
            </button>
            <button
              type="button"
              onClick={() => setConfirmDelete(false)}
              className="px-1.5 py-0.5 text-slate-500 hover:text-slate-800 text-xs"
            >
              Cancel
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setConfirmDelete(true)}
            className="text-rose-600 hover:text-rose-700 flex items-center gap-1 text-xs font-semibold px-1 py-0.5 rounded hover:bg-rose-50 transition"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span>Remove Chip</span>
          </button>
        )}

        <button
          type="button"
          onClick={onClose}
          className="px-3 py-1.5 bg-brand-600 hover:bg-brand-700 text-white rounded-lg font-semibold text-xs shadow-xs transition"
        >
          Done
        </button>
      </div>
    </div>
  );
};
