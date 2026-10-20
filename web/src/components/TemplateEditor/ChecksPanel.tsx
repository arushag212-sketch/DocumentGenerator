import React, { useState } from 'react';
import { CheckCircle2, AlertTriangle, AlertCircle, RefreshCw, ShieldCheck, Wrench } from 'lucide-react';
import { api } from '../../api/client';

export interface CheckFinding {
  id: string;
  type: 'error' | 'warning' | 'info' | 'suggestion';
  category: string;
  title: string;
  message: string;
  actionLabel?: string;
  fix?: any;
}

interface ChecksPanelProps {
  editor: any;
  fields: any[];
  clubId?: string;
  templateId?: string;
  theme?: string;
  onAutoFix?: (findingId: string) => void;
  onApplyChatAction?: (action: any) => void;
}

export const ChecksPanel: React.FC<ChecksPanelProps> = ({
  editor,
  fields,
  clubId,
  templateId,
  theme,
  onAutoFix,
  onApplyChatAction,
}) => {
  const [isRunning, setIsRunning] = useState(false);
  const [findings, setFindings] = useState<CheckFinding[]>([]);
  const [score, setScore] = useState<number | null>(null);
  const [hasRun, setHasRun] = useState(false);

  const runChecks = async () => {
    if (!editor) return;
    setIsRunning(true);

    try {
      if (clubId && templateId) {
        const res = await api.documents.checkTemplate(clubId, templateId, {
          editor_json: editor.getJSON(),
          fields,
          theme: theme || 'modern_academic',
        });

        if (res && res.findings) {
          const mapped: CheckFinding[] = res.findings.map((f: any) => ({
            id: f.id,
            type: f.severity === 'suggestion' ? 'info' : (f.severity as any),
            category: f.rule?.replace(/_/g, ' ') || 'Quality',
            title: f.title || 'Audit Finding',
            message: f.message,
            actionLabel: f.fix?.summary || 'Apply Fix',
            fix: f.fix,
          }));
          setFindings(mapped);
          setScore(res.score ?? 100);
          setHasRun(true);
          setIsRunning(false);
          return;
        }
      }
    } catch {
      // Fallback to local heuristic check
    }

    // Local heuristic fallback
    const newFindings: CheckFinding[] = [];
    const docText = editor.state.doc.textBetween(0, editor.state.doc.content.size, ' ');

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
        title: 'Unfilled Official Wording',
        message: `${officialPlaceholders} block(s) contain placeholder text requiring real official wording.`,
        actionLabel: 'Use Standard Request Text',
        fix: {
          type: 'insert_clause',
          payload: { text: 'We respectfully submit this proposal for your kind consideration and approval.' },
        },
      });
    }

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
        title: 'Missing Essential Fields',
        message: `Essential fields missing from document: ${missingEssential.join(', ')}.`,
        actionLabel: 'Insert Missing Field Chip',
        fix: {
          type: 'insert_chip',
          payload: { field_key: missingEssential[0] },
        },
      });
    }

    if (docText.trim().length < 20) {
      newFindings.push({
        id: 'short_doc',
        type: 'warning',
        category: 'Completeness',
        title: 'Document Too Short',
        message: 'The document appears to have very little text. Ensure required sections are included.',
      });
    }

    if (/ {3,}/.test(docText)) {
      newFindings.push({
        id: 'extra_spaces',
        type: 'info',
        category: 'Formatting',
        title: 'Multiple Consecutive Spaces',
        message: 'Multiple consecutive spaces detected. Spacing can be normalized.',
        actionLabel: 'Normalize Spaces',
      });
    }

    setFindings(newFindings);
    setScore(Math.max(100 - newFindings.length * 15, 30));
    setHasRun(true);
    setIsRunning(false);
  };

  const handleFix = (finding: CheckFinding) => {
    if (finding.fix && onApplyChatAction) {
      onApplyChatAction({
        type: finding.fix.action_type || finding.fix.type,
        payload: finding.fix.payload || {},
      });
    } else if (onAutoFix) {
      onAutoFix(finding.id);
    }
    // Remove fixed finding
    setFindings((prev) => prev.filter((f) => f.id !== finding.id));
  };

  return (
    <div className="flex flex-col h-full bg-slate-50/50 p-4 space-y-4 text-xs overflow-y-auto">
      {/* Top Banner */}
      <div className="flex items-center justify-between pb-3 border-b border-slate-200">
        <div>
          <h3 className="font-bold text-slate-800 text-xs flex items-center gap-1.5">
            <ShieldCheck className="w-4 h-4 text-brand-600" />
            Document Quality Checks
          </h3>
          <p className="text-xs text-slate-500">
            Rules, protocol & pre-flight validation
          </p>
        </div>
        <button
          onClick={runChecks}
          disabled={isRunning}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-brand-600 hover:bg-brand-700 disabled:opacity-50 text-white rounded-lg text-xs font-semibold shadow-sm transition"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isRunning ? 'animate-spin' : ''}`} />
          Run Checks
        </button>
      </div>

      {score !== null && hasRun && (
        <div className="p-3 bg-white rounded-xl border border-slate-200 shadow-sm flex items-center justify-between">
          <div>
            <span className="text-[11px] font-bold text-slate-400">Compliance Score</span>
            <div className="text-xl font-semibold text-slate-800">{score}<span className="text-xs font-normal text-slate-400">/100</span></div>
          </div>
          <span className={`px-2.5 py-1 rounded-full text-xs font-bold ${score >= 90 ? 'bg-emerald-100 text-emerald-800' : score >= 70 ? 'bg-amber-100 text-amber-800' : 'bg-rose-100 text-rose-800'}`}>
            {score >= 90 ? 'Ready to Publish' : score >= 70 ? 'Needs Attention' : 'Action Required'}
          </span>
        </div>
      )}

      {!hasRun ? (
        <div className="flex-1 flex flex-col items-center justify-center text-center p-6 text-slate-500">
          <ShieldCheck className="w-10 h-10 text-slate-300 mb-2" />
          <p className="font-semibold text-slate-700 text-xs mb-1">
            Check your document for compliance
          </p>
          <p className="text-xs text-slate-400 max-w-xs mb-4">
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
          <p className="text-xs text-emerald-700">
            No missing required fields or formatting issues were detected. Document is ready for publishing!
          </p>
        </div>
      ) : (
        <div className="space-y-2.5">
          <div className="text-xs text-slate-600 font-medium">
            Found {findings.length} item(s) to review:
          </div>
          {findings.map((f) => (
            <div
              key={f.id}
              className={`p-3 rounded-xl border bg-white shadow-sm space-y-2 ${
                f.type === 'error'
                  ? 'border-rose-200'
                  : f.type === 'warning'
                  ? 'border-amber-200'
                  : 'border-slate-200'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-1.5 font-bold text-xs text-slate-800">
                  {f.type === 'error' && <AlertCircle className="w-3.5 h-3.5 text-rose-600" />}
                  {f.type === 'warning' && <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />}
                  {f.type === 'info' && <ShieldCheck className="w-3.5 h-3.5 text-brand-600" />}
                  {f.title}
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
              <p className="text-xs text-slate-600">{f.message}</p>
              {f.actionLabel && (
                <button
                  onClick={() => handleFix(f)}
                  className="inline-flex items-center gap-1 px-2.5 py-1 bg-brand-50 hover:bg-brand-100 text-brand-700 font-semibold rounded text-[11px] transition"
                >
                  <Wrench className="w-3 h-3 text-brand-600" />
                  {f.actionLabel}
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
