import React from 'react';
import { Lock, Trash2 } from 'lucide-react';

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
  if (!chipPopover) return null;

  return (
    <div
      style={{ top: `${chipPopover.top}px`, left: `${chipPopover.left}px` }}
      className="fixed z-50 bg-white border border-slate-200 rounded-xl shadow-2xl p-3.5 w-72 text-xs space-y-3 animate-in fade-in"
    >
      <div className="flex items-center justify-between pb-1.5 border-b border-slate-100">
        <span className="font-bold text-slate-800 truncate">
          Field: {chipPopover.fieldName}
        </span>
        <button onClick={onClose} className="text-slate-400 hover:text-slate-600 font-bold">
          ✕
        </button>
      </div>

      <div>
        <label className="block text-xs font-semibold text-slate-600 mb-0.5">Label</label>
        <input
          type="text"
          value={chipPopover.label}
          onChange={(e) => onUpdateChip({ label: e.target.value })}
          className="w-full px-2 py-1 border border-slate-200 rounded text-xs focus:ring-1 focus:ring-brand-500 focus:outline-none"
        />
      </div>

      <div className="flex items-center justify-between pt-1">
        <span className="text-xs font-semibold text-slate-600">Importance</span>
        <button
          onClick={() => onToggleRequired(!chipPopover.required)}
          className={`px-2 py-0.5 rounded text-[11px] font-bold transition ${
            chipPopover.required
              ? 'bg-rose-100 text-rose-700 border border-rose-300'
              : 'bg-slate-100 text-slate-600'
          }`}
        >
          {chipPopover.required ? 'Essential' : 'Optional'}
        </button>
      </div>

      <div className="flex items-center justify-between pt-1">
        <span className="text-xs font-semibold text-slate-600">Sensitive</span>
        <button
          onClick={() => onToggleSensitive(!chipPopover.sensitive)}
          className={`px-2 py-0.5 rounded text-[11px] font-bold transition flex items-center gap-1 ${
            chipPopover.sensitive
              ? 'bg-amber-100 text-amber-800 border border-amber-300'
              : 'bg-slate-100 text-slate-600'
          }`}
        >
          <Lock className="w-2.5 h-2.5" />
          {chipPopover.sensitive ? 'Yes' : 'No'}
        </button>
      </div>

      <div className="pt-2 border-t border-slate-100 flex justify-between items-center">
        <button
          onClick={onDelete}
          className="text-rose-600 hover:text-rose-700 flex items-center gap-1 text-xs font-semibold"
        >
          <Trash2 className="w-3.5 h-3.5" />
          Remove Chip
        </button>
        <button
          onClick={onClose}
          className="px-2.5 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded font-semibold text-xs"
        >
          Done
        </button>
      </div>
    </div>
  );
};
