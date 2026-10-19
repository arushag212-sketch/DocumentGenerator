import React from 'react';
import { Check, CornerUpLeft } from 'lucide-react';
import { actionPreview } from './editorAssistant';
import type { EditorAssistantAction } from './editorAssistant';

export interface EditorActionItemProps {
  action: EditorAssistantAction;
  actionId: string;
  applied: boolean;
  rejected: boolean;
  disabled?: boolean;
  onApply: () => void;
  onReject: () => void;
  onUndo?: () => void;
  onClarifySelect: (option: string) => void;
}

export const EditorActionItem: React.FC<EditorActionItemProps> = ({
  action,
  actionId,
  applied,
  rejected,
  disabled = false,
  onApply,
  onReject,
  onUndo,
  onClarifySelect,
}) => {
  if (action.type === 'ask_clarifying_question') {
    return (
      <div key={actionId} className="rounded-lg border border-indigo-200 bg-indigo-50/70 p-2 text-indigo-950">
        <p className="font-semibold text-xs mb-1.5">{action.payload.question}</p>
        <div className="flex flex-wrap gap-1">
          {(action.payload.options || []).map((opt) => (
            <button
              key={opt}
              onClick={() => onClarifySelect(opt)}
              className="rounded bg-white px-2 py-0.5 text-[10px] font-medium text-indigo-700 border border-indigo-200 hover:bg-indigo-100"
            >
              {opt}
            </button>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div key={actionId} className="rounded-lg border border-slate-200 bg-white p-2 text-slate-800">
      <p className="text-[11px] font-semibold text-slate-900">{action.summary}</p>
      <p className="text-[10px] text-slate-500 mt-0.5 line-clamp-3">{actionPreview(action)}</p>

      <div className="mt-1.5 flex items-center gap-1.5">
        {!applied && !rejected && (
          <>
            <button
              onClick={onApply}
              disabled={disabled}
              className="inline-flex items-center gap-1 rounded bg-indigo-600 px-2 py-0.5 text-[10px] font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
            >
              <Check className="h-2.5 w-2.5" />
              Apply
            </button>
            <button
              onClick={onReject}
              disabled={disabled}
              className="rounded bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-600 hover:bg-slate-200 disabled:opacity-50"
            >
              Reject
            </button>
          </>
        )}
        {applied && (
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded">
              <Check className="h-3 w-3" /> Applied
            </span>
            {onUndo && (
              <button
                onClick={onUndo}
                className="inline-flex items-center gap-1 text-[10px] font-semibold text-slate-600 hover:text-slate-900 underline"
              >
                <CornerUpLeft className="h-2.5 w-2.5" /> Undo
              </button>
            )}
          </div>
        )}
        {rejected && <span className="text-[10px] text-slate-400 italic">Dismissed</span>}
      </div>
    </div>
  );
};
