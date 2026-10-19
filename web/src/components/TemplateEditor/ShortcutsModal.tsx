import React from 'react';
import { X, Command } from 'lucide-react';

interface ShortcutsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const ShortcutsModal: React.FC<ShortcutsModalProps> = ({ isOpen, onClose }) => {
  if (!isOpen) return null;

  const shortcuts = [
    { category: 'Text Formatting', items: [
      { key: 'Ctrl + B', label: 'Bold text' },
      { key: 'Ctrl + I', label: 'Italic text' },
      { key: 'Ctrl + U', label: 'Underline text' },
      { key: 'Ctrl + Shift + L', label: 'Align left' },
      { key: 'Ctrl + Shift + E', label: 'Align center' },
      { key: 'Ctrl + Shift + R', label: 'Align right' },
      { key: 'Ctrl + Shift + J', label: 'Justify' },
    ]},
    { category: 'Structure & Blocks', items: [
      { key: '/', label: 'Open Slash Commands palette' },
      { key: 'Enter', label: 'New paragraph' },
      { key: 'Shift + Enter', label: 'Soft line break' },
      { key: 'Tab / Shift + Tab', label: 'Indent / Outdent table cells or lists' },
    ]},
    { category: 'History & Editing', items: [
      { key: 'Ctrl + Z', label: 'Undo action (single transaction)' },
      { key: 'Ctrl + Y / Ctrl + Shift + Z', label: 'Redo action' },
      { key: 'Ctrl + F', label: 'Find and Replace' },
      { key: 'Ctrl + S', label: 'Save draft now' },
      { key: 'Escape', label: 'Close popover or dialog' },
    ]},
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <div className="bg-white rounded-xl shadow-2xl border border-slate-200 max-w-lg w-full overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100 bg-slate-50">
          <div className="flex items-center gap-2">
            <Command className="w-5 h-5 text-indigo-600" />
            <h3 className="font-bold text-slate-800 text-sm">Keyboard Shortcuts Cheat Sheet</h3>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-md text-slate-400 hover:text-slate-600 hover:bg-slate-200/60 transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-5 max-h-[70vh] overflow-y-auto space-y-5">
          {shortcuts.map((group, idx) => (
            <div key={idx}>
              <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">
                {group.category}
              </h4>
              <div className="space-y-1.5">
                {group.items.map((item, itemIdx) => (
                  <div
                    key={itemIdx}
                    className="flex items-center justify-between text-xs py-1 px-2 rounded hover:bg-slate-50 transition"
                  >
                    <span className="text-slate-700">{item.label}</span>
                    <kbd className="px-2 py-0.5 font-mono text-[11px] font-semibold text-slate-600 bg-slate-100 border border-slate-300 rounded shadow-sm">
                      {item.key}
                    </kbd>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        <div className="px-5 py-3 border-t border-slate-100 bg-slate-50 text-right">
          <button
            onClick={onClose}
            className="px-4 py-1.5 bg-slate-800 hover:bg-slate-900 text-white rounded text-xs font-semibold transition"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
};
