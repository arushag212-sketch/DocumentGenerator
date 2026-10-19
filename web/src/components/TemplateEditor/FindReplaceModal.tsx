import React, { useState } from 'react';
import { X, Search, Replace, Check } from 'lucide-react';

interface FindReplaceModalProps {
  isOpen: boolean;
  onClose: () => void;
  editor: any;
}

export const FindReplaceModal: React.FC<FindReplaceModalProps> = ({ isOpen, onClose, editor }) => {
  const [findText, setFindText] = useState('');
  const [replaceText, setReplaceText] = useState('');
  const [matchCount, setMatchCount] = useState<number | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  if (!isOpen) return null;

  const countMatches = (query: string) => {
    if (!editor || !query) {
      setMatchCount(null);
      return;
    }
    const docText = editor.state.doc.textBetween(0, editor.state.doc.content.size, ' ');
    const regex = new RegExp(query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
    const matches = docText.match(regex);
    setMatchCount(matches ? matches.length : 0);
  };

  const handleFindChange = (val: string) => {
    setFindText(val);
    countMatches(val);
    setMessage(null);
  };

  const handleReplaceAll = () => {
    if (!editor || !findText) return;

    let count = 0;
    const escaped = findText.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const regex = new RegExp(escaped, 'gi');

    editor.commands.command(({ tr, state, dispatch }: any) => {
      let modified = false;
      state.doc.descendants((node: any, pos: number) => {
        if (node.isText && node.text) {
          if (regex.test(node.text)) {
            const newText = node.text.replace(regex, () => {
              count++;
              return replaceText;
            });
            tr.insertText(newText, pos, pos + node.nodeSize);
            modified = true;
          }
        }
      });
      if (modified && dispatch) {
        dispatch(tr);
      }
      return modified;
    });

    setMessage(`Replaced ${count} occurrence(s).`);
    countMatches(findText);
  };

  return (
    <div className="fixed top-20 right-20 z-50 bg-white rounded-xl shadow-2xl border border-slate-200 w-80 p-4 animate-in fade-in duration-150">
      <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-100">
        <div className="flex items-center gap-2">
          <Search className="w-4 h-4 text-indigo-600" />
          <h4 className="font-bold text-slate-800 text-xs">Find and Replace</h4>
        </div>
        <button
          onClick={onClose}
          className="p-1 text-slate-400 hover:text-slate-600 rounded transition"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>

      <div className="space-y-3">
        <div>
          <label className="block text-[11px] font-semibold text-slate-600 mb-1">Find</label>
          <div className="relative">
            <input
              type="text"
              value={findText}
              onChange={(e) => handleFindChange(e.target.value)}
              placeholder="Search in template..."
              className="w-full text-xs px-2.5 py-1.5 border border-slate-300 rounded focus:ring-1 focus:ring-indigo-500 focus:outline-none"
              autoFocus
            />
            {matchCount !== null && (
              <span className="absolute right-2 top-1.5 text-[10px] text-slate-400 font-mono">
                {matchCount} found
              </span>
            )}
          </div>
        </div>

        <div>
          <label className="block text-[11px] font-semibold text-slate-600 mb-1">Replace With</label>
          <input
            type="text"
            value={replaceText}
            onChange={(e) => setReplaceText(e.target.value)}
            placeholder="New text..."
            className="w-full text-xs px-2.5 py-1.5 border border-slate-300 rounded focus:ring-1 focus:ring-indigo-500 focus:outline-none"
          />
        </div>

        {message && (
          <div className="text-[11px] text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded flex items-center gap-1.5">
            <Check className="w-3.5 h-3.5" />
            {message}
          </div>
        )}

        <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
          <button
            onClick={onClose}
            className="px-3 py-1 text-xs text-slate-600 hover:bg-slate-100 rounded transition"
          >
            Cancel
          </button>
          <button
            onClick={handleReplaceAll}
            disabled={!findText || matchCount === 0}
            className="px-3 py-1 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-xs font-semibold rounded shadow-sm transition flex items-center gap-1"
          >
            <Replace className="w-3 h-3" />
            Replace All
          </button>
        </div>
      </div>
    </div>
  );
};
