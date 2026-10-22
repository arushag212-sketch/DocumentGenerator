import React, { useState } from 'react';
import { Upload, FileText, Check, AlertTriangle, ArrowRight, X, Loader2, Tag, Wand2 } from 'lucide-react';
import { api } from '../../api/client';

interface TemplateImportModalProps {
  clubId: string | number;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (templateId: string) => void;
}

export const TemplateImportModal: React.FC<TemplateImportModalProps> = ({
  clubId,
  isOpen,
  onClose,
  onSuccess,
}) => {
  const [mode, setMode] = useState<'text' | 'docx'>('text');
  const [step, setStep] = useState<'input' | 'review'>('input');
  const [rawText, setRawText] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [templateName, setTemplateName] = useState('');
  const [parsedData, setParsedData] = useState<{
    editor_json: any;
    fields: any[];
    unsupported_elements?: string[];
    name: string;
  } | null>(null);
  const [confirmedFieldKeys, setConfirmedFieldKeys] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      let res: any;
      if (mode === 'text') {
        if (!rawText.trim()) return;
        res = await api.documents.importTextTemplate(clubId, {
          text: rawText.trim(),
          name: templateName.trim() || undefined,
        });
      } else {
        if (!selectedFile) return;
        res = await api.documents.importDocxTemplate(clubId, selectedFile);
      }
      setParsedData(res);
      setTemplateName(res.name || templateName || 'Imported Template');
      // Confirm all fields by default
      const keys = new Set<string>((res.fields || []).map((f: any) => f.key));
      setConfirmedFieldKeys(keys);
      setStep('review');
    } catch (err: any) {
      setError(err.message || 'Failed to import and analyze document.');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateTemplate = async () => {
    if (!parsedData) return;
    setLoading(true);
    setError(null);
    try {
      // 1. Create blank template
      const tmpl = await api.documents.createBlankTemplate(clubId, {
        name: templateName.trim() || parsedData.name || 'Imported Template',
        category: 'Official Event Documents',
      });

      // 2. Filter confirmed fields
      const finalFields = (parsedData.fields || []).filter((f) => confirmedFieldKeys.has(f.key));

      // 3. Save draft with imported editor_json and fields
      await api.documents.saveTemplateDraft(clubId, tmpl.id, {
        name: tmpl.name,
        category: tmpl.category,
        editor_json: parsedData.editor_json,
        fields: finalFields,
      });

      onSuccess(tmpl.id);
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to finalize imported template.');
    } finally {
      setLoading(false);
    }
  };

  const toggleField = (key: string) => {
    setConfirmedFieldKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in">
      <div className="bg-white rounded-xl shadow-2xl max-w-2xl w-full max-h-[85vh] sm:max-h-[90vh] overflow-hidden flex flex-col border border-slate-200">
        {/* Header */}
        <div className="px-5 py-4 sm:px-6 bg-white border-b border-slate-200 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="p-2 bg-brand-600 text-white rounded-xl shadow-xs">
              <Upload className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-bold text-slate-800 text-base">Import Existing Document</h3>
              <p className="text-xs text-slate-500">
                {step === 'input' ? 'Paste existing text or upload a Word document' : 'Review detected variable fields'}
              </p>
            </div>
          </div>
          <button onClick={onClose} className="p-2.5 sm:p-2 min-w-[44px] min-h-[44px] flex items-center justify-center text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 transition" aria-label="Close dialog">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="p-4 sm:p-6 space-y-5 flex-1 overflow-y-auto">
          {error && (
            <div className="p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-xl flex items-center justify-between">
              <span>{error}</span>
              <button onClick={() => setError(null)} className="text-red-400 hover:text-red-600">
                <X className="w-4 h-4" />
              </button>
            </div>
          )}

          {step === 'input' && (
            <form onSubmit={handleAnalyze} className="space-y-4">
              {/* Import Mode Switcher */}
              <div className="flex bg-slate-100 p-1 rounded-xl text-xs font-semibold">
                <button
                  type="button"
                  onClick={() => setMode('text')}
                  className={`flex-1 py-1.5 rounded-lg transition flex items-center justify-center gap-1.5 ${
                    mode === 'text' ? 'bg-white text-brand-600 shadow-xs' : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  <FileText className="w-4 h-4" />
                  <span>Paste Text</span>
                </button>
                <button
                  type="button"
                  onClick={() => setMode('docx')}
                  className={`flex-1 py-1.5 rounded-lg transition flex items-center justify-center gap-1.5 ${
                    mode === 'docx' ? 'bg-white text-brand-600 shadow-xs' : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  <Upload className="w-4 h-4" />
                  <span>Upload DOCX</span>
                </button>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                  Template Name (Optional)
                </label>
                <input
                  type="text"
                  value={templateName}
                  onChange={(e) => setTemplateName(e.target.value)}
                  placeholder="e.g. IEEE Workshop Permission Letter"
                  className="w-full text-xs px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl focus:bg-white focus:outline-none"
                />
              </div>

              {mode === 'text' ? (
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                    Paste Notice or Letter Text
                  </label>
                  <textarea
                    value={rawText}
                    onChange={(e) => setRawText(e.target.value)}
                    placeholder="Paste the full text of an official notice, sanction letter, or proposal..."
                    rows={8}
                    required
                    className="w-full text-xs p-3 bg-slate-50 border border-slate-300 rounded-xl focus:ring-2 focus:ring-brand-500 focus:bg-white focus:outline-none font-sans"
                  />
                </div>
              ) : (
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                    Upload Word Document (.docx)
                  </label>
                  <div className="border-2 border-dashed border-slate-300 hover:border-brand-500 rounded-xl p-8 text-center cursor-pointer bg-slate-50/50 transition">
                    <input
                      type="file"
                      accept=".docx"
                      onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                      className="hidden"
                      id="docx-file-input"
                    />
                    <label htmlFor="docx-file-input" className="cursor-pointer flex flex-col items-center">
                      <Upload className="w-8 h-8 text-slate-400 mb-2" />
                      <span className="text-xs font-bold text-slate-700">
                        {selectedFile ? selectedFile.name : 'Click to select or drag and drop DOCX file'}
                      </span>
                      <span className="text-xs text-slate-500 mt-1">
                        Extracts paragraphs, tables, bold/italic formatting, and variables
                      </span>
                    </label>
                  </div>
                </div>
              )}

              <div className="pt-2 flex justify-end">
                <button
                  type="submit"
                  disabled={loading || (mode === 'text' ? !rawText.trim() : !selectedFile)}
                  className="flex items-center gap-2 px-5 py-2.5 bg-brand-600 hover:bg-brand-700 disabled:opacity-50 text-white text-xs font-bold rounded-xl shadow-sm transition"
                >
                  {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Wand2 className="w-4 h-4" />}
                  <span>Detect Variables & Import</span>
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            </form>
          )}

          {step === 'review' && parsedData && (
            <div className="space-y-4">
              {parsedData.unsupported_elements && parsedData.unsupported_elements.length > 0 && (
                <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-amber-900 text-xs space-y-1">
                  <div className="flex items-center gap-1.5 font-bold">
                    <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                    <span>Import Notice: Some Word elements were simplified</span>
                  </div>
                  <ul className="list-disc list-inside text-xs pl-1">
                    {parsedData.unsupported_elements.map((el, idx) => (
                      <li key={idx}>{el}</li>
                    ))}
                  </ul>
                </div>
              )}

              <div>
                <h4 className="text-xs font-bold text-slate-800 mb-1 flex items-center gap-1.5">
                  <Tag className="w-4 h-4 text-brand-600" />
                  <span>Proposed Dynamic Variable Fields ({parsedData.fields.length})</span>
                </h4>
                <p className="text-xs text-slate-500 mb-2">
                  Check the fields you want to convert into dynamic fillable chips:
                </p>

                {parsedData.fields.length === 0 ? (
                  <div className="p-4 bg-slate-50 rounded-xl text-center text-xs text-slate-500">
                    No automatic variable patterns detected. You can add chips manually inside the editor.
                  </div>
                ) : (
                  <div className="grid grid-cols-2 gap-2 max-h-48 overflow-y-auto p-1">
                    {parsedData.fields.map((f: any) => {
                      const isChecked = confirmedFieldKeys.has(f.key);
                      return (
                        <button
                          key={f.key}
                          type="button"
                          onClick={() => toggleField(f.key)}
                          className={`p-2.5 rounded-xl border text-left text-xs transition flex items-center justify-between ${
                            isChecked
                              ? 'border-brand-600 bg-brand-50/70 text-brand-900 font-bold'
                              : 'border-slate-200 bg-white text-slate-600 opacity-60'
                          }`}
                        >
                          <div>
                            <span className="block truncate">{f.label}</span>
                            <span className="text-xs text-slate-400 font-mono font-normal">
                              {f.key} ({f.type})
                            </span>
                          </div>
                          {isChecked && <Check className="w-4 h-4 text-brand-600 shrink-0" />}
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>

              <div className="pt-3 border-t border-slate-200 flex items-center justify-between">
                <button
                  type="button"
                  onClick={() => setStep('input')}
                  className="px-4 py-2 text-xs font-medium text-slate-600 hover:text-slate-800 rounded-xl"
                >
                  Back
                </button>
                <button
                  type="button"
                  onClick={handleCreateTemplate}
                  disabled={loading}
                  className="flex items-center gap-2 px-5 py-2.5 bg-brand-600 hover:bg-brand-700 text-white text-xs font-bold rounded-xl shadow-md transition"
                >
                  {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
                  <span>Open in Template Editor</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
