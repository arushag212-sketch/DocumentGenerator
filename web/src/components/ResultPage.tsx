import React, { useState, useEffect, useMemo } from 'react';
import {
  CheckCircle2,
  Download,
  FileText,
  ArrowLeft,
  ExternalLink,
  Archive,
  FileCode,
  ImageIcon,
  Loader2,
  Sparkles,
  AlertCircle,
  Plus,
  Trash2,
  RefreshCw,
  Layers,
  ChevronDown,
  X,
  Info,
} from 'lucide-react';
import { api } from '../api/client';
import {
  HomeGenerateResponse,
  HomeCreateResponse,
  HomeGeneratedDoc,
  EditableField,
  TableColumn,
} from '../types';

interface ResultPageProps {
  clubId: string | number;
  result: HomeCreateResponse | HomeGenerateResponse;
  onEditDetails: () => void;
}

function isBlankValue(val: any): boolean {
  if (val === null || val === undefined) return true;
  if (typeof val === 'string') {
    const s = val.trim();
    return s === '' || /_{4,}/.test(s);
  }
  if (Array.isArray(val)) {
    return val.length === 0;
  }
  return false;
}

function isAiDraftField(fieldKey: string, val: any): boolean {
  const k = fieldKey.toLowerCase();
  if (k === 'description' || k === 'objectives' || k.includes('objective') || k.includes('body_text')) {
    return typeof val === 'string' && val.trim().length > 0;
  }
  return false;
}

/**
 * Editable Table component for table/list fields (budget items, winners, attendees, etc.)
 */
const TableFieldEditor: React.FC<{
  field: EditableField;
  value: any[];
  onChange: (val: any[]) => void;
  isMissing: boolean;
}> = ({ field, value, onChange, isMissing }) => {
  const columns: TableColumn[] = useMemo(() => {
    if (field.columns && field.columns.length > 0) {
      return field.columns;
    }
    // Default columns heuristic
    const k = field.key.toLowerCase();
    if (k.includes('budget') || k.includes('bill') || k.includes('expense')) {
      return [
        { key: 'item', label: 'Item / Description' },
        { key: 'amount', label: 'Amount (₹)', type: 'number' },
      ];
    }
    if (k.includes('winner') || k.includes('prize')) {
      return [
        { key: 'name', label: 'Participant / Team Name' },
        { key: 'prize', label: 'Position / Prize' },
      ];
    }
    if (k.includes('agenda')) {
      return [
        { key: 'time', label: 'Time' },
        { key: 'topic', label: 'Topic / Discussion' },
      ];
    }
    return [{ key: 'name', label: 'Name / Detail' }];
  }, [field]);

  const items = useMemo(() => {
    if (!Array.isArray(value)) return [];
    return value.map((it) => {
      if (typeof it === 'string') {
        const primaryKey = columns[0]?.key || 'name';
        return { [primaryKey]: it };
      }
      return typeof it === 'object' && it !== null ? { ...it } : {};
    });
  }, [value, columns]);

  const handleCellChange = (rowIndex: number, colKey: string, cellVal: any) => {
    const updated = [...items];
    updated[rowIndex] = {
      ...updated[rowIndex],
      [colKey]: cellVal,
    };
    // If the original field was string array and we only have 1 column:
    if (columns.length === 1 && typeof value?.[0] === 'string') {
      onChange(updated.map((r) => r[columns[0].key] || ''));
    } else {
      onChange(updated);
    }
  };

  const handleAddRow = () => {
    const newRow: Record<string, any> = {};
    columns.forEach((c) => {
      newRow[c.key] = c.type === 'number' ? 0 : '';
    });
    if (columns.length === 1 && typeof value?.[0] === 'string') {
      onChange([...(Array.isArray(value) ? value : []), '']);
    } else {
      onChange([...items, newRow]);
    }
  };

  const handleRemoveRow = (rowIndex: number) => {
    const updated = items.filter((_, idx) => idx !== rowIndex);
    if (columns.length === 1 && typeof value?.[0] === 'string') {
      onChange(updated.map((r) => r[columns[0].key] || ''));
    } else {
      onChange(updated);
    }
  };

  return (
    <div className={`space-y-2 rounded-xl border p-3 ${isMissing ? 'border-amber-300 bg-amber-50/30' : 'border-slate-200 bg-slate-50/50'}`}>
      <div className="flex items-center justify-between text-xs font-semibold text-slate-700">
        <span>{field.label} ({items.length} {items.length === 1 ? 'row' : 'rows'})</span>
        <button
          type="button"
          onClick={handleAddRow}
          className="px-2.5 py-1 text-xs font-bold text-brand-700 bg-brand-50 hover:bg-brand-100 rounded-lg flex items-center gap-1 transition-colors border border-brand-200"
        >
          <Plus className="w-3.5 h-3.5" />
          Add row
        </button>
      </div>

      {items.length === 0 ? (
        <div className="text-center py-4 bg-white rounded-lg border border-dashed border-slate-300 text-xs text-slate-500">
          No entries yet. Shown as a clean blank section in the document.
          <button
            type="button"
            onClick={handleAddRow}
            className="block mx-auto mt-2 text-brand-700 font-semibold hover:underline"
          >
            + Add first row
          </button>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
          <table className="w-full text-xs text-left">
            <thead className="bg-slate-100 text-slate-600 font-bold border-b border-slate-200">
              <tr>
                <th className="px-2.5 py-2 w-8 text-center text-slate-400">#</th>
                {columns.map((c) => (
                  <th key={c.key} className="px-2.5 py-2">
                    {c.label}
                  </th>
                ))}
                <th className="px-2 py-2 w-10 text-center"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {items.map((row, rIdx) => (
                <tr key={rIdx} className="hover:bg-slate-50/50">
                  <td className="px-2.5 py-2 text-center text-slate-400 font-mono text-[11px]">{rIdx + 1}</td>
                  {columns.map((col) => (
                    <td key={col.key} className="px-2 py-1.5">
                      <input
                        type={col.type === 'number' ? 'number' : 'text'}
                        value={row[col.key] ?? ''}
                        onChange={(e) =>
                          handleCellChange(
                            rIdx,
                            col.key,
                            col.type === 'number' ? (e.target.value === '' ? '' : Number(e.target.value)) : e.target.value
                          )
                        }
                        placeholder={`Enter ${col.label.toLowerCase()}`}
                        className="w-full px-2 py-1 bg-white border border-slate-200 rounded text-xs focus:ring-1 focus:ring-brand-700 focus:outline-none"
                      />
                    </td>
                  ))}
                  <td className="px-2 py-1.5 text-center">
                    <button
                      type="button"
                      onClick={() => handleRemoveRow(rIdx)}
                      className="p-1 text-slate-400 hover:text-red-600 rounded transition-colors"
                      title="Remove row"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export const ResultPage: React.FC<ResultPageProps> = ({
  clubId,
  result: initialResult,
  onEditDetails,
}) => {
  const [documents, setDocuments] = useState<HomeGeneratedDoc[]>(initialResult.documents || []);
  const [selectedDocIndex, setSelectedDocIndex] = useState(0);
  const [previewMode, setPreviewMode] = useState<'image' | 'pdf'>('image');
  const [availableTemplates, setAvailableTemplates] = useState<any[]>([]);
  const [showAddDocDropdown, setShowAddDocDropdown] = useState(false);

  // Form values for the currently active document
  const [formValues, setFormValues] = useState<Record<string, any>>({});
  const [savingDoc, setSavingDoc] = useState(false);
  const [applyingAll, setApplyingAll] = useState(false);
  const [addingDoc, setAddingDoc] = useState(false);
  const [actionNotice, setActionNotice] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // AI instruct prompt box
  const [aiPrompt, setAiPrompt] = useState('');
  const [aiInstructing, setAiInstructing] = useState(false);
  const [aiExplanation, setAiExplanation] = useState<string | null>(null);

  const activeDoc: HomeGeneratedDoc | undefined = documents[selectedDocIndex] || documents[0];

  // Fetch available templates to support "Add document"
  useEffect(() => {
    if (clubId) {
      api.documents
        .listTemplates(clubId)
        .then((data) => {
          setAvailableTemplates((data || []).filter((t: any) => t.status === 'published'));
        })
        .catch(() => {});
    }
  }, [clubId]);

  // Synchronize form values whenever active document changes
  useEffect(() => {
    if (activeDoc) {
      const initVals: Record<string, any> = {};
      (activeDoc.editable_fields || []).forEach((f) => {
        initVals[f.key] = f.value;
      });
      setFormValues(initVals);
      setActionNotice(null);
      setAiExplanation(null);
    }
  }, [activeDoc?.id, activeDoc?.version_no]);

  // Compute missing blanks count for the active document
  const missingCount = useMemo(() => {
    if (!activeDoc?.editable_fields) return 0;
    return activeDoc.editable_fields.filter((f) => {
      const currentVal = formValues[f.key] !== undefined ? formValues[f.key] : f.value;
      return isBlankValue(currentVal);
    }).length;
  }, [activeDoc?.editable_fields, formValues]);

  // Save changes to current document (POST /documents/{id}/revise)
  const handleSaveChanges = async () => {
    if (!activeDoc) return;
    setSavingDoc(true);
    setActionNotice(null);
    try {
      // Build changes payload
      const changes: Record<string, any> = { ...formValues };
      await api.documents.revise(clubId, activeDoc.id, changes, 'Updated in Review screen');

      // Fetch the updated document with fresh page images and editable fields
      const updatedDoc = await api.documents.get(clubId, activeDoc.id);

      setDocuments((prev) =>
        prev.map((d, idx) => {
          if (idx !== selectedDocIndex) return d;
          return {
            ...d,
            version_no: updatedDoc.current_version_no,
            page_count: updatedDoc.page_count,
            page_images: updatedDoc.page_images,
            pdf_url: updatedDoc.pdf_url,
            docx_url: updatedDoc.docx_url,
            preview_url: updatedDoc.page_images?.[0] || d.preview_url,
            editable_fields: updatedDoc.editable_fields,
            missing_fields: (updatedDoc.editable_fields || [])
              .filter((f) => isBlankValue(f.value))
              .map((f) => f.key),
          };
        })
      );

      setActionNotice({
        type: 'success',
        message: `Saved as Version ${updatedDoc.current_version_no}. Reference number (${activeDoc.ref_no}) preserved and preview updated!`,
      });
    } catch (err: any) {
      setActionNotice({
        type: 'error',
        message: err?.detail?.message || err?.message || 'Could not save changes to the document.',
      });
    } finally {
      setSavingDoc(false);
    }
  };

  // Apply to all documents from the same event
  const handleApplyToAll = async () => {
    if (!initialResult.event_id) return;
    setApplyingAll(true);
    setActionNotice(null);
    try {
      const res = await api.home.applyAll(clubId, {
        event_id: initialResult.event_id,
        updates: formValues,
      });

      // Update local documents list with new versions
      setDocuments(res.documents);

      setActionNotice({
        type: 'success',
        message: `Updated shared details across all ${res.updated_documents_count} documents in this request!`,
      });
    } catch (err: any) {
      setActionNotice({
        type: 'error',
        message: err?.detail?.message || err?.message || 'Failed to apply updates to all documents.',
      });
    } finally {
      setApplyingAll(false);
    }
  };

  // Ask AI to modify fields
  const handleAiInstruct = async () => {
    if (!aiPrompt.trim() || !activeDoc) return;
    setAiInstructing(true);
    setActionNotice(null);
    setAiExplanation(null);
    try {
      const res = await api.home.aiInstruct(clubId, {
        instruction: aiPrompt.trim(),
        current_data: formValues,
        template_slug: activeDoc.template_slug,
      });

      if (res.proposed_updates && Object.keys(res.proposed_updates).length > 0) {
        setFormValues((prev) => ({
          ...prev,
          ...res.proposed_updates,
        }));
        setAiExplanation(res.explanation || 'Updated fields as requested.');
        setAiPrompt('');
      } else {
        setAiExplanation('No field changes were needed for that instruction.');
      }
    } catch (err: any) {
      setActionNotice({
        type: 'error',
        message: err?.detail?.message || err?.message || 'AI update failed. You can edit the fields directly below.',
      });
    } finally {
      setAiInstructing(false);
    }
  };

  // Add another document to the event
  const handleAddDocument = async (templateId: string) => {
    if (!initialResult.event_id) return;
    setAddingDoc(true);
    setShowAddDocDropdown(false);
    setActionNotice(null);
    try {
      const newDoc = await api.home.addDocument(clubId, {
        event_id: initialResult.event_id,
        template_id: templateId,
      });
      setDocuments((prev) => [...prev, newDoc]);
      setSelectedDocIndex(documents.length);
      setActionNotice({
        type: 'success',
        message: `Added ${newDoc.title} (${newDoc.ref_no})!`,
      });
    } catch (err: any) {
      setActionNotice({
        type: 'error',
        message: err?.detail?.message || err?.message || 'Could not add document.',
      });
    } finally {
      setAddingDoc(false);
    }
  };

  // Remove a document from the session view
  const handleRemoveDoc = (indexToRemove: number) => {
    if (documents.length <= 1) return;
    setDocuments((prev) => prev.filter((_, idx) => idx !== indexToRemove));
    if (selectedDocIndex >= indexToRemove && selectedDocIndex > 0) {
      setSelectedDocIndex(selectedDocIndex - 1);
    }
  };

  const assumptions = (initialResult as HomeCreateResponse).assumptions || [];
  const notice = (initialResult as HomeCreateResponse).notice;

  // Unselected templates for "+ Add document"
  const existingSlugs = new Set(documents.map((d) => d.template_slug));
  const addableTemplates = availableTemplates.filter(
    (t) => !existingSlugs.has(t.slug) && !existingSlugs.has(t.id)
  );

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6 space-y-5">
      {/* Top Banner & Navigation Header */}
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-5 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold text-emerald-800 bg-emerald-50 px-2.5 py-0.5 rounded-full border border-emerald-200 flex items-center gap-1">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
              AI Drafted
            </span>
            <span className="text-xs text-slate-400 font-mono">
              Batch: {initialResult.batch_id?.slice(0, 8)}
            </span>
          </div>
          <h1 className="text-xl font-bold text-slate-900">
            {initialResult.event_title || 'Generated Documents'}
          </h1>
          <p className="text-xs text-slate-500">
            Review the drafted documents, update any missing details, and save. Reference numbers remain unbroken.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <button
            type="button"
            onClick={onEditDetails}
            className="px-3.5 py-2 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-xl flex items-center gap-1.5 transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            Create another
          </button>

          {initialResult.zip_url && (
            <a
              href={initialResult.zip_url}
              download
              className="px-4 py-2 text-xs font-bold text-white bg-brand-700 hover:bg-brand-800 rounded-xl shadow-sm flex items-center gap-2 transition-colors"
            >
              <Archive className="w-4 h-4" />
              Download All (.zip)
            </a>
          )}
        </div>
      </div>

      {/* Notice Banner (e.g. LLM Fallback) */}
      {notice && (
        <div className="p-3.5 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-900 flex items-start gap-2.5">
          <Info className="w-4 h-4 text-amber-700 shrink-0 mt-0.5" />
          <span>{notice}</span>
        </div>
      )}

      {/* Assumptions Pills */}
      {assumptions.length > 0 && (
        <div className="bg-slate-50 border border-slate-200 rounded-xl p-3 flex flex-wrap items-center gap-2">
          <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1">
            <Sparkles className="w-3 h-3 text-brand-700" />
            Club defaults applied:
          </span>
          {assumptions.map((item, idx) => (
            <span
              key={idx}
              className="text-xs font-medium bg-white border border-slate-200 text-slate-700 px-2.5 py-0.5 rounded-full shadow-2xs"
            >
              {item}
            </span>
          ))}
        </div>
      )}

      {/* Action Notification (Inline Success or Error) */}
      {actionNotice && (
        <div
          className={`p-3.5 rounded-xl border flex items-start justify-between gap-2.5 text-xs sm:text-sm animate-in fade-in ${
            actionNotice.type === 'success'
              ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
              : 'bg-red-50 border-red-200 text-red-900'
          }`}
        >
          <div className="flex items-center gap-2">
            {actionNotice.type === 'success' ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            ) : (
              <AlertCircle className="w-4 h-4 text-red-600 shrink-0" />
            )}
            <span>{actionNotice.message}</span>
          </div>
          <button
            type="button"
            onClick={() => setActionNotice(null)}
            className="hover:opacity-70 text-slate-500"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Document Selection Tabs + Add Document Button */}
      <div className="flex flex-wrap items-center gap-2 border-b border-slate-200 pb-2">
        {documents.map((doc, idx) => {
          const isSelected = selectedDocIndex === idx;
          const docMissingCount = (doc.editable_fields || []).filter((f) => isBlankValue(f.value)).length;
          return (
            <div
              key={doc.id}
              className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-bold border transition-all cursor-pointer ${
                isSelected
                  ? 'bg-brand-700 text-white border-brand-700 shadow-sm'
                  : 'bg-white text-slate-700 border-slate-200 hover:border-slate-300'
              }`}
              onClick={() => setSelectedDocIndex(idx)}
            >
              <FileText className={`w-3.5 h-3.5 ${isSelected ? 'text-white' : 'text-slate-400'}`} />
              <span>{doc.title}</span>
              <span
                className={`font-mono text-[11px] px-1.5 py-0.5 rounded ${
                  isSelected ? 'bg-brand-800 text-brand-100' : 'bg-slate-100 text-slate-600'
                }`}
              >
                v{doc.version_no}
              </span>

              {docMissingCount > 0 && (
                <span
                  className={`text-[10px] px-1.5 py-0.5 rounded-full font-semibold ${
                    isSelected ? 'bg-amber-400 text-slate-900' : 'bg-amber-100 text-amber-800'
                  }`}
                  title={`${docMissingCount} blank fields`}
                >
                  {docMissingCount} blank
                </span>
              )}

              {documents.length > 1 && (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleRemoveDoc(idx);
                  }}
                  className={`hover:text-red-500 ml-1 ${isSelected ? 'text-brand-200' : 'text-slate-400'}`}
                  title="Remove document from view"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          );
        })}

        {/* Add Another Document Dropdown */}
        {addableTemplates.length > 0 && (
          <div className="relative">
            <button
              type="button"
              disabled={addingDoc}
              onClick={() => setShowAddDocDropdown(!showAddDocDropdown)}
              className="px-3 py-2 text-xs font-bold text-slate-600 hover:text-brand-700 bg-slate-100 hover:bg-slate-200 rounded-xl flex items-center gap-1.5 transition-colors border border-dashed border-slate-300"
            >
              {addingDoc ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Plus className="w-3.5 h-3.5" />
              )}
              <span>Add document</span>
              <ChevronDown className="w-3.5 h-3.5" />
            </button>

            {showAddDocDropdown && (
              <div className="absolute left-0 mt-1 w-64 bg-white rounded-xl shadow-lg border border-slate-200 py-1.5 z-30 animate-in fade-in">
                <div className="px-3 py-1 text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                  Generate with same details:
                </div>
                {addableTemplates.map((t) => (
                  <button
                    key={t.id || t.slug}
                    type="button"
                    onClick={() => handleAddDocument(t.slug || t.id)}
                    className="w-full px-3 py-2 text-left text-xs text-slate-700 hover:bg-brand-50 hover:text-brand-900 font-medium flex items-center gap-2 transition-colors"
                  >
                    <FileText className="w-3.5 h-3.5 text-slate-400" />
                    <span>{t.name}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Main Workspace Grid: Document Preview (Left) vs Details Panel (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Rendered Document Preview (7 cols) */}
        <div className="lg:col-span-7 space-y-3">
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden flex flex-col">
            {/* Preview Toolbar */}
            <div className="p-3 bg-slate-50 border-b border-slate-200 flex flex-wrap items-center justify-between gap-2 text-xs">
              <div className="flex items-center gap-2">
                <span className="font-bold text-slate-900">{activeDoc?.title}</span>
                <span className="font-mono text-brand-700 bg-brand-50 border border-brand-200 px-2 py-0.5 rounded text-[11px]">
                  {activeDoc?.ref_no}
                </span>
              </div>

              <div className="flex items-center gap-2">
                {/* View switcher: Page View vs PDF */}
                <div className="flex items-center bg-slate-200/80 p-0.5 rounded-lg">
                  <button
                    type="button"
                    onClick={() => setPreviewMode('image')}
                    className={`px-2.5 py-1 rounded-md flex items-center gap-1 font-semibold transition-all ${
                      previewMode === 'image'
                        ? 'bg-white text-slate-900 shadow-xs'
                        : 'text-slate-600 hover:text-slate-900'
                    }`}
                  >
                    <ImageIcon className="w-3.5 h-3.5" />
                    Page View
                  </button>
                  <button
                    type="button"
                    onClick={() => setPreviewMode('pdf')}
                    className={`px-2.5 py-1 rounded-md flex items-center gap-1 font-semibold transition-all ${
                      previewMode === 'pdf'
                        ? 'bg-white text-slate-900 shadow-xs'
                        : 'text-slate-600 hover:text-slate-900'
                    }`}
                  >
                    <FileText className="w-3.5 h-3.5" />
                    PDF
                  </button>
                </div>

                {/* Downloads */}
                {activeDoc && (
                  <div className="flex items-center gap-1.5 border-l border-slate-200 pl-2">
                    <a
                      href={activeDoc.pdf_url}
                      download
                      className="px-2.5 py-1 text-xs font-bold text-red-700 bg-red-50 hover:bg-red-100 border border-red-200 rounded-md flex items-center gap-1 transition-colors"
                      title="Download PDF"
                    >
                      <Download className="w-3 h-3" />
                      PDF
                    </a>
                    <a
                      href={activeDoc.docx_url}
                      download
                      className="px-2.5 py-1 text-xs font-bold text-brand-700 bg-brand-50 hover:bg-brand-100 border border-brand-200 rounded-md flex items-center gap-1 transition-colors"
                      title="Download Word"
                    >
                      <FileCode className="w-3 h-3" />
                      Word
                    </a>
                    <a
                      href={`${activeDoc.pdf_url}?disposition=inline`}
                      target="_blank"
                      rel="noreferrer"
                      className="p-1 text-slate-400 hover:text-slate-700 rounded"
                      title="Open in new tab"
                    >
                      <ExternalLink className="w-3.5 h-3.5" />
                    </a>
                  </div>
                )}
              </div>
            </div>

            {/* Preview Viewport */}
            <div className="bg-slate-100 p-4 min-h-[640px] max-h-[820px] overflow-y-auto flex flex-col items-center gap-4">
              {activeDoc ? (
                previewMode === 'image' ? (
                  activeDoc.page_images && activeDoc.page_images.length > 0 ? (
                    activeDoc.page_images.map((pageSrc, idx) => (
                      <div key={pageSrc + idx} className="w-full max-w-[620px] bg-white rounded-lg shadow-md border border-slate-200 overflow-hidden">
                        <img
                          src={pageSrc}
                          alt={`${activeDoc.title} page ${idx + 1}`}
                          className="w-full h-auto object-contain block"
                          loading={idx === 0 ? 'eager' : 'lazy'}
                        />
                      </div>
                    ))
                  ) : (
                    <div className="w-full max-w-[620px] bg-white rounded-lg shadow-md border border-slate-200 overflow-hidden">
                      <img
                        src={activeDoc.preview_url}
                        alt={activeDoc.title}
                        className="w-full h-auto object-contain block"
                      />
                    </div>
                  )
                ) : (
                  <iframe
                    src={`${activeDoc.pdf_url.includes('?') ? activeDoc.pdf_url : `${activeDoc.pdf_url}?`}disposition=inline#toolbar=0`}
                    title={activeDoc.title}
                    className="w-full h-[760px] rounded-lg border border-slate-300 bg-white"
                  />
                )
              ) : (
                <div className="text-center py-20 text-slate-400 text-xs">
                  No document selected
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right Column: Editable Details Panel (5 cols) */}
        <div className="lg:col-span-5 space-y-4">
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-5 space-y-4">
            {/* Header: Title and Missing Count Indicator */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">
                  Document Details
                </h2>
                <span className="text-xs text-slate-400">
                  v{activeDoc?.version_no}
                </span>
              </div>

              {missingCount > 0 ? (
                <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-900 flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />
                  <span>
                    <strong>{missingCount} details still blank</strong> — shown as blank lines in the document.
                  </span>
                </div>
              ) : (
                <div className="p-2.5 bg-emerald-50 border border-emerald-200 rounded-xl text-xs text-emerald-800 flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span>All details filled.</span>
                </div>
              )}
            </div>

            {/* "Ask AI to change…" box */}
            <div className="bg-gradient-to-r from-brand-50/70 to-indigo-50/70 border border-brand-100 rounded-xl p-3.5 space-y-2">
              <div className="flex items-center gap-1.5 text-xs font-bold text-brand-900">
                <Sparkles className="w-3.5 h-3.5 text-brand-700" />
                <span>Ask AI to change details</span>
              </div>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={aiPrompt}
                  onChange={(e) => setAiPrompt(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      handleAiInstruct();
                    }
                  }}
                  placeholder="e.g. make the date 16 October and add Dr. Mehta as resource person"
                  className="flex-1 px-3 py-1.5 bg-white border border-brand-200 rounded-lg text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-brand-700"
                  disabled={aiInstructing}
                />
                <button
                  type="button"
                  onClick={handleAiInstruct}
                  disabled={aiInstructing || !aiPrompt.trim()}
                  className="px-3 py-1.5 bg-brand-700 hover:bg-brand-800 disabled:opacity-50 text-white font-bold text-xs rounded-lg transition-colors shrink-0 flex items-center gap-1"
                >
                  {aiInstructing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : 'Update'}
                </button>
              </div>

              {aiExplanation && (
                <div className="p-2 bg-white/90 border border-brand-200 rounded-lg text-[11px] text-brand-900 flex items-center gap-1.5">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                  <span>{aiExplanation}</span>
                </div>
              )}
            </div>

            {/* Editable Fields Form */}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSaveChanges();
              }}
              className="space-y-4 max-h-[520px] overflow-y-auto pr-1"
            >
              {(activeDoc?.editable_fields || []).map((field) => {
                const val = formValues[field.key] !== undefined ? formValues[field.key] : field.value;
                const isBlank = isBlankValue(val);
                const isAiDraft = isAiDraftField(field.key, val);

                // Table / list fields
                if (field.type === 'table' || field.type === 'list' || Array.isArray(field.value)) {
                  return (
                    <TableFieldEditor
                      key={field.key}
                      field={field}
                      value={Array.isArray(val) ? val : []}
                      onChange={(updated) => setFormValues((prev) => ({ ...prev, [field.key]: updated }))}
                      isMissing={isBlank}
                    />
                  );
                }

                // Textarea for long text or descriptions/objectives
                const isLong =
                  field.type === 'textarea' ||
                  field.type === 'long_text' ||
                  field.key.includes('description') ||
                  field.key.includes('objective') ||
                  (typeof val === 'string' && val.length > 80);

                return (
                  <div key={field.key} className="space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <label htmlFor={`field-${field.key}`} className="font-semibold text-slate-800">
                        {field.label}
                        {field.required && <span className="text-red-500 ml-0.5">*</span>}
                      </label>
                      <div className="flex items-center gap-1">
                        {isAiDraft && (
                          <span className="text-[10px] font-bold text-purple-800 bg-purple-50 border border-purple-200 px-1.5 py-0.5 rounded">
                            AI draft
                          </span>
                        )}
                        {isBlank && (
                          <span className="text-[10px] font-semibold text-amber-800 bg-amber-50 border border-amber-200 px-1.5 py-0.5 rounded">
                            Not filled — shown as blank line
                          </span>
                        )}
                      </div>
                    </div>

                    {isLong ? (
                      <textarea
                        id={`field-${field.key}`}
                        rows={3}
                        value={val ?? ''}
                        onChange={(e) => setFormValues((prev) => ({ ...prev, [field.key]: e.target.value }))}
                        className={`w-full text-xs p-2.5 rounded-xl border focus:bg-white focus:outline-none focus:ring-1 focus:ring-brand-700 transition-colors ${
                          isBlank
                            ? 'bg-amber-50/40 border-amber-300'
                            : 'bg-slate-50 border-slate-200'
                        }`}
                      />
                    ) : field.type === 'date' ? (
                      <input
                        type="date"
                        id={`field-${field.key}`}
                        value={val ?? ''}
                        onChange={(e) => setFormValues((prev) => ({ ...prev, [field.key]: e.target.value }))}
                        className={`w-full text-xs px-3 py-2 rounded-xl border focus:bg-white focus:outline-none focus:ring-1 focus:ring-brand-700 transition-colors ${
                          isBlank
                            ? 'bg-amber-50/40 border-amber-300'
                            : 'bg-slate-50 border-slate-200'
                        }`}
                      />
                    ) : field.type === 'time' ? (
                      <input
                        type="time"
                        id={`field-${field.key}`}
                        value={val ?? ''}
                        onChange={(e) => setFormValues((prev) => ({ ...prev, [field.key]: e.target.value }))}
                        className={`w-full text-xs px-3 py-2 rounded-xl border focus:bg-white focus:outline-none focus:ring-1 focus:ring-brand-700 transition-colors ${
                          isBlank
                            ? 'bg-amber-50/40 border-amber-300'
                            : 'bg-slate-50 border-slate-200'
                        }`}
                      />
                    ) : field.type === 'money' || field.type === 'currency' ? (
                      <div className="relative">
                        <span className="absolute left-3 top-2 text-xs text-slate-400">₹</span>
                        <input
                          type="number"
                          step="0.01"
                          id={`field-${field.key}`}
                          value={val ?? ''}
                          onChange={(e) => setFormValues((prev) => ({ ...prev, [field.key]: e.target.value }))}
                          className={`w-full text-xs pl-7 pr-3 py-2 rounded-xl border focus:bg-white focus:outline-none focus:ring-1 focus:ring-brand-700 transition-colors ${
                            isBlank
                              ? 'bg-amber-50/40 border-amber-300'
                              : 'bg-slate-50 border-slate-200'
                          }`}
                        />
                      </div>
                    ) : field.type === 'number' || field.type === 'integer' ? (
                      <input
                        type="number"
                        id={`field-${field.key}`}
                        value={val ?? ''}
                        onChange={(e) => setFormValues((prev) => ({ ...prev, [field.key]: e.target.value }))}
                        className={`w-full text-xs px-3 py-2 rounded-xl border focus:bg-white focus:outline-none focus:ring-1 focus:ring-brand-700 transition-colors ${
                          isBlank
                            ? 'bg-amber-50/40 border-amber-300'
                            : 'bg-slate-50 border-slate-200'
                        }`}
                      />
                    ) : (
                      <input
                        type="text"
                        id={`field-${field.key}`}
                        value={val ?? ''}
                        onChange={(e) => setFormValues((prev) => ({ ...prev, [field.key]: e.target.value }))}
                        className={`w-full text-xs px-3 py-2 rounded-xl border focus:bg-white focus:outline-none focus:ring-1 focus:ring-brand-700 transition-colors ${
                          isBlank
                            ? 'bg-amber-50/40 border-amber-300'
                            : 'bg-slate-50 border-slate-200'
                        }`}
                      />
                    )}
                  </div>
                );
              })}

              {/* Action Buttons inside Details Panel */}
              <div className="pt-3 border-t border-slate-100 space-y-2 sticky bottom-0 bg-white">
                <button
                  type="submit"
                  disabled={savingDoc}
                  className="w-full py-2.5 bg-brand-700 hover:bg-brand-800 disabled:opacity-50 text-white font-bold text-xs rounded-xl shadow-sm flex items-center justify-center gap-1.5 transition-colors"
                >
                  {savingDoc ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Saving new version…</span>
                    </>
                  ) : (
                    <>
                      <RefreshCw className="w-3.5 h-3.5" />
                      <span>Save changes & update preview</span>
                    </>
                  )}
                </button>

                {documents.length > 1 && (
                  <button
                    type="button"
                    onClick={handleApplyToAll}
                    disabled={applyingAll}
                    className="w-full py-2 bg-slate-100 hover:bg-slate-200 text-slate-800 font-bold text-xs rounded-xl flex items-center justify-center gap-1.5 transition-colors border border-slate-200"
                    title="Propagates event title, dates, venue and participants across all documents"
                  >
                    {applyingAll ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Layers className="w-3.5 h-3.5 text-slate-500" />
                    )}
                    <span>Apply shared details to all documents</span>
                  </button>
                )}
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
};
