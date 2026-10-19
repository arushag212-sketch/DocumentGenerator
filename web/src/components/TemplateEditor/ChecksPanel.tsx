import React, { useState } from 'react';
import { CheckCircle2, AlertTriangle, AlertCircle, RefreshCw, ShieldCheck } from 'lucide-react';

export interface CheckFinding {
  id: string;
  type: 'error' | 'warning' | 'info';
  category: string;
  message: string;
  actionLabel?: string;
  fix?: () => void;
}

interface ChecksPanelProps {
  editor: any;
  fields: any[];
  onAutoFix?: (findingId: string) => void;
}

export const ChecksPanel: React.FC<ChecksPanelProps> = ({ editor, fields }) => {
  const [isRunning, setIsRunning] = useState(false);
  const [findings, setFindings] = useState<CheckFinding[]>([]);
  const [hasRun, setHasRun] = useState(false);

  const runChecks = () => {
    if (!editor) return;
    setIsRunning(true);
    const newFindings: CheckFinding[] = [];

    const docText = editor.state.doc.textBetween(0, editor.state.doc.content.size, ' ');

    // 1. Check for official wording placeholders unfilled
    let officialPlaceholders = 0;
    editor.state.doc.descendants((node: any) => {
      if (node.attrs?.official_wording_required || node.text?.includes('Add official wording here')) {
        officialPlaceholders++;
      }
    });
    if (officialPlaceholders > 0) {
      newFindings.push({
        id: 'official_placeholder',
        type: 'warning',
        category: 'Official Protocol',
        message: `${officialPlaceholders} block(s) contain placeholder text requiring real official wording before publishing.`,
        actionLabel: 'Review Official Wording',
      });
    }

    // 2. Check for missing essential fields
    const essentialKeys = fields.filter((f) => f.importance === 'essential' || f.required).map((f) => f.key);
    const presentKeys = new Set<string>();
    editor.state.doc.descendants((node: any) => {
      if (node.type.name === 'fieldChip' && node.attrs?.fieldName) {
        presentKeys.add(node.attrs.fieldName);
      }
    });

    const missingEssential = essentialKeys.filter((k) => !presentKeys.has(k));
    if (missingEssential.length > 0) {
      newFindings.push({
        id: 'missing_essential',
        type: 'error',
        category: 'Required Fields',
        message: `Essential fields missing from document: ${missingEssential.join(', ')}.`,
        actionLabel: 'Insert Missing Fields',
      });
    }

    // 3. Check for empty template
    if (docText.trim().length < 20) {
      newFindings.push({
        id: 'short_doc',
        type: 'warning',
        category: 'Completeness',
        message: 'The document appears to have very little text. Ensure required sections are included.',
      });
    }

    // 4. Inconsistent punctuation or multiple spaces
    if (/ {3,}/.test(docText)) {
      newFindings.push({
        id: 'extra_spaces',
        type: 'info',
        category: 'Formatting',
        message: 'Multiple consecutive spaces detected. Consider normalizing paragraph spacing.',
      });
    }

    setTimeout(() => {
      setFindings(newFindings);
      setIsRunning(false);
      setHasRun(true);
    }, 400);
  };

  return (
    <div className="flex flex-col h-full bg-slate-50/50 p-4 space-y-4 text-xs overflow-y-auto">
      {/* Top Banner */}
      <div className="flex items-center justify-between pb-3 border-b border-slate-200">
        <div>
          <h3 className="font-bold text-slate-800 text-xs uppercase tracking-wider">
            Document Quality Checks
          </h3>
          <p className="text-[11px] text-slate-500">
            Rules and protocol pre-flight validation
          </p>
        </div>
        <button
          onClick={runChecks}
          disabled={isRunning}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-lg text-xs font-semibold shadow-sm transition"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isRunning ? 'animate-spin' : ''}`} />
          Run Checks
        </button>
      </div>

      {!hasRun ? (
        <div className="flex-1 flex flex-col items-center justify-center text-center p-6 text-slate-500">
          <ShieldCheck className="w-10 h-10 text-slate-300 mb-2" />
          <p className="font-semibold text-slate-700 text-xs mb-1">
            Check your document for compliance
          </p>
          <p className="text-[11px] text-slate-400 max-w-xs mb-4">
            Scans for missing required fields, official wording gaps, and typography consistency.
          </p>
          <button
            onClick={runChecks}
            className="px-4 py-2 bg-white border border-slate-300 text-slate-700 hover:bg-slate-50 font-semibold rounded-lg text-xs shadow-sm transition"
          >
            Start Check
          </button>
        </div>
      ) : findings.length === 0 ? (
        <div className="p-4 bg-emerald-50 rounded-xl border border-emerald-200 text-center">
          <CheckCircle2 className="w-8 h-8 text-emerald-600 mx-auto mb-2" />
          <h4 className="font-bold text-emerald-900 text-xs mb-1">All Checks Passed</h4>
          <p className="text-[11px] text-emerald-700">
            No missing required fields or formatting issues were detected. Document is ready for publishing!
          </p>
        </div>
      ) : (
        <div className="space-y-2.5">
          <div className="text-[11px] text-slate-600 font-medium">
            Found {findings.length} item(s) to review:
          </div>
          {findings.map((f) => (
            <div
              key={f.id}
              className={`p-3 rounded-xl border bg-white shadow-sm space-y-1.5 ${
                f.type === 'error'
                  ? 'border-rose-200'
                  : f.type === 'warning'
                  ? 'border-amber-200'
                  : 'border-slate-200'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-1.5 font-bold text-[11px] text-slate-800">
                  {f.type === 'error' && <AlertCircle className="w-3.5 h-3.5 text-rose-600" />}
                  {f.type === 'warning' && <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />}
                  {f.type === 'info' && <ShieldCheck className="w-3.5 h-3.5 text-indigo-600" />}
                  {f.category}
                </span>
                <span
                  className={`text-[9px] uppercase font-bold px-1.5 py-0.5 rounded ${
                    f.type === 'error'
                      ? 'bg-rose-50 text-rose-700'
                      : f.type === 'warning'
                      ? 'bg-amber-50 text-amber-700'
                      : 'bg-slate-100 text-slate-600'
                  }`}
                >
                  {f.type}
                </span>
              </div>
              <p className="text-[11px] text-slate-600">{f.message}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
