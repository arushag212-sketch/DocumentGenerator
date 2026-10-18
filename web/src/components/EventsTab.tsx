import React, { useState, useEffect } from 'react';
import {
  Calendar,
  FileText,
  Edit2,
  RefreshCw,
  Loader2,
  AlertCircle,
  CheckCircle,
  Wand2,
  Sparkles,
  CheckSquare,
  Square,
  Download,
  FolderArchive,
  Info,
  Layers,
  HelpCircle,
  Plus,
  Trash2,
  CheckCircle2,
  ChevronRight,
} from 'lucide-react';
import { api } from '../api/client';
import { GeneratedDocument } from '../types';

interface EventsTabProps {
  clubId: string | number;
  onViewDocument: (doc: GeneratedDocument) => void;
  onNewDocumentForEvent?: (templateId: string, eventId: string) => void;
}

export const EventsTab: React.FC<EventsTabProps> = ({
  clubId,
  onViewDocument,
  onNewDocumentForEvent,
}) => {
  const [events, setEvents] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // New Document for Event Modal State
  const [newDocModalEvent, setNewDocModalEvent] = useState<any | null>(null);
  const [availableTemplates, setAvailableTemplates] = useState<any[]>([]);
  const [loadingTemplates, setLoadingTemplates] = useState<boolean>(false);

  // Describe Your Event / Batch Generation States
  const [eventDescription, setEventDescription] = useState('');
  const [analyzing, setAnalyzing] = useState(false);
  const [recommendation, setRecommendation] = useState<any | null>(null);
  const [selectedTemplateIds, setSelectedTemplateIds] = useState<string[]>([]);
  const [formInputs, setFormInputs] = useState<Record<string, any>>({});
  const [datesConfirmed, setDatesConfirmed] = useState(false);
  const [numberingConfirmed, setNumberingConfirmed] = useState(false);
  const [generatingBatch, setGeneratingBatch] = useState(false);
  const [batchProgress, setBatchProgress] = useState<string | null>(null);
  const [batchResult, setBatchResult] = useState<any | null>(null);
  const [showOtherTemplates, setShowOtherTemplates] = useState(false);

  // Structured Lists for repeat_per (winners, bills)
  const [winners, setWinners] = useState<Array<{ name: string; roll_no: string; amount: number; position?: string }>>([
    { name: '', roll_no: '', amount: 1000, position: '1st Place' },
  ]);
  const [bills, setBills] = useState<Array<{ bill_no: string; vendor: string; amount: number; particulars?: string }>>([
    { bill_no: '', vendor: '', amount: 500, particulars: 'Event Supplies' },
  ]);

  // Edit Event State
  const [editingEvent, setEditingEvent] = useState<any | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [editEventCode, setEditEventCode] = useState('');
  const [editVenue, setEditVenue] = useState('');
  const [updateDocuments, setUpdateDocuments] = useState(true);
  const [saving, setSaving] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const fetchEvents = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.events.list(clubId);
      setEvents(res.items || []);
    } catch (err: any) {
      setError(err.message || 'Failed to load events');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEvents();
  }, [clubId]);

  // Step 1: Analyze & Recommend
  const handleAnalyzeEvent = async () => {
    if (!eventDescription.trim()) return;
    try {
      setAnalyzing(true);
      setError(null);
      setBatchResult(null);
      const res = await api.events.recommend(clubId, {
        text: eventDescription.trim(),
      });
      setRecommendation(res);
      // Pre-select recommended templates
      const initialSelected = res.templates.filter((t: any) => t.recommended).map((t: any) => t.template_id);
      setSelectedTemplateIds(initialSelected);

      // Pre-fill form inputs with extracted fields
      setFormInputs({ ...(res.extracted_data || {}) });

      if (res.extracted_data?.winners && Array.isArray(res.extracted_data.winners) && res.extracted_data.winners.length > 0) {
        setWinners(res.extracted_data.winners);
      }
      if (res.extracted_data?.bills && Array.isArray(res.extracted_data.bills) && res.extracted_data.bills.length > 0) {
        setBills(res.extracted_data.bills);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to analyze event description');
    } finally {
      setAnalyzing(false);
    }
  };

  // Toggle template checkbox
  const toggleTemplateSelection = async (tmplId: string) => {
    const updated = selectedTemplateIds.includes(tmplId)
      ? selectedTemplateIds.filter((id) => id !== tmplId)
      : [...selectedTemplateIds, tmplId];
    setSelectedTemplateIds(updated);

    // Refresh grouped missing fields with updated selection
    try {
      const refreshed = await api.events.recommend(clubId, {
        text: eventDescription.trim(),
        explicit_data: formInputs,
        selected_template_ids: updated,
      });
      setRecommendation((prev: any) => ({
        ...prev,
        grouped_missing_fields: refreshed.grouped_missing_fields,
      }));
    } catch {
      // silent fallback
    }
  };

  const handleAcceptAiDraft = (key: string) => {
    const currentVal = formInputs[key] || '';
    const cleaned = currentVal.replace(/^\[AI-drafted,\s*review\]\s*/i, '').trim();
    setFormInputs((prev) => ({
      ...prev,
      [key]: cleaned,
    }));
  };

  const hasUnacceptedAiDraft = Object.entries(formInputs).some(
    ([_, v]) => typeof v === 'string' && v.includes('[AI-drafted')
  );

  const handleAcceptAllAiDrafts = () => {
    setFormInputs((prev) => {
      const updated: Record<string, any> = { ...prev };
      Object.entries(updated).forEach(([k, v]) => {
        if (typeof v === 'string' && v.includes('[AI-drafted')) {
          updated[k] = v.replace(/^\[AI-drafted,\s*review\]\s*/i, '').trim();
        }
      });
      return updated;
    });
  };

  const emptyRequiredFields = (recommendation?.grouped_missing_fields || []).filter((f: any) => {
    if (f.defer_ok || f.key === 'dates_confirmation' || f.key === 'document_date') return false;
    const val = formInputs[f.key];
    return val === undefined || val === null || String(val).trim() === '';
  });

  const handleOpenNewDocModal = async (ev: any) => {
    setNewDocModalEvent(ev);
    try {
      setLoadingTemplates(true);
      const tmpls = await api.documents.listTemplates(clubId);
      setAvailableTemplates(tmpls.filter((t: any) => t.status === 'published'));
    } catch {
      // fallback
    } finally {
      setLoadingTemplates(false);
    }
  };

  const handleSelectTemplateForEvent = (templateId: string) => {
    if (newDocModalEvent && onNewDocumentForEvent) {
      onNewDocumentForEvent(templateId, newDocModalEvent.id);
      setNewDocModalEvent(null);
    }
  };

  // Step 2: Batch Generate Selected Documents
  const handleGenerateBatch = async () => {
    if (selectedTemplateIds.length === 0) {
      alert('Please select at least one document to generate.');
      return;
    }

    if (hasUnacceptedAiDraft) {
      alert('Please accept or edit all AI-drafted content before generating.');
      return;
    }

    if (!numberingConfirmed) {
      alert('Please confirm reference numbers to be reserved.');
      return;
    }

    try {
      setGeneratingBatch(true);
      setError(null);
      setBatchProgress('Reserving official reference numbers...');

      await new Promise((r) => setTimeout(r, 400));
      setBatchProgress('Rendering DOCX & official PDF documents...');

      // Prepare payload without automatic stripping of AI draft tags
      const mergedData: Record<string, any> = { ...formInputs, dates_confirmed: datesConfirmed };
      if (winners.length > 0 && winners[0].name) {
        mergedData.winners = winners;
      }
      if (bills.length > 0 && bills[0].vendor) {
        mergedData.bills = bills;
      }

      const res = await api.events.generateBatch(clubId, {
        selected_template_ids: selectedTemplateIds,
        event_data: mergedData,
        event_title: mergedData.event_name || 'Campus Event',
      });

      setBatchProgress('Packaging ZIP archive and updating audit trail...');
      await new Promise((r) => setTimeout(r, 400));

      setBatchResult(res);
      setBatchProgress(null);
      await fetchEvents();
    } catch (err: any) {
      setError(err.message || 'Failed to batch generate documents');
      setBatchProgress(null);
    } finally {
      setGeneratingBatch(false);
    }
  };

  const handleOpenEdit = (ev: any) => {
    setEditingEvent(ev);
    setEditTitle(ev.title);
    setEditEventCode(ev.event_code || '');
    setEditVenue(ev.record?.venue || '');
    setUpdateDocuments(true);
    setSuccessMsg(null);
  };

  const handleSaveEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingEvent) return;

    try {
      setSaving(true);
      setError(null);
      const mergedRecord = { ...(editingEvent.record || {}), venue: editVenue };
      const res = await api.events.update(
        clubId,
        editingEvent.id,
        {
          title: editTitle,
          event_code: editEventCode,
          record: mergedRecord,
        },
        updateDocuments
      );
      if (updateDocuments && res.documents && res.documents.length > 0) {
        const docList = res.documents
          .map((d: any) => `${d.title || d.template_slug} (v${d.current_version_no})`)
          .join(', ');
        setSuccessMsg(`Event updated. Re-rendered ${res.documents.length} document(s): ${docList}`);
      } else {
        setSuccessMsg('Event updated successfully.');
      }
      setEditingEvent(null);
      setEvents((prev) => prev.map((ev) => (ev.id === editingEvent.id ? res : ev)));
      await fetchEvents();
    } catch (err: any) {
      setError(err.message || 'Failed to update event');
    } finally {
      setSaving(false);
    }
  };

  const handleViewDoc = async (docId: string) => {
    try {
      const doc = await api.documents.get(clubId, docId);
      onViewDocument(doc);
    } catch (err: any) {
      alert(`Could not load document: ${err.message}`);
    }
  };

  return (
    <div className="space-y-8">
      {successMsg && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-xs sm:text-sm text-emerald-800 flex items-center gap-2 font-medium">
          <CheckCircle className="w-4 h-4 flex-shrink-0 text-emerald-600" />
          <span>{successMsg}</span>
        </div>
      )}

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-xs sm:text-sm text-red-800 flex items-center gap-2 font-medium">
          <AlertCircle className="w-4 h-4 flex-shrink-0 text-red-600" />
          <span>{error}</span>
        </div>
      )}

      {/* SECTION 1: DESCRIBE YOUR EVENT & BATCH GENERATION */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="bg-gradient-to-r from-[#1b365d] to-[#254677] p-6 text-white">
          <div className="flex items-center gap-2.5">
            <Sparkles className="w-5 h-5 text-amber-300" />
            <h2 className="text-xl font-bold">Events & Coordinated Document Packages</h2>
          </div>
          <p className="text-xs sm:text-sm text-slate-200 mt-1 max-w-2xl">
            Describe your event in natural language. The system extracts canonical parameters, recommends the required documents based on stage and schema triggers, and creates the complete package in one job.
          </p>
        </div>

        <div className="p-6 space-y-6">
          {/* Input Box */}
          <div className="space-y-3">
            <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider">
              Event Description
            </label>
            <textarea
              rows={3}
              value={eventDescription}
              onChange={(e) => setEventDescription(e.target.value)}
              placeholder="e.g. We are conducting a two-day Web Development Workshop on 14-15 October in Seminar Hall for around 120 students."
              className="w-full border border-slate-300 rounded-lg p-3 text-xs sm:text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-[#1b365d] focus:border-transparent"
            />

            {/* Quick Prefill Samples */}
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <span className="text-slate-400 text-[11px] font-semibold">Try sample:</span>
              <button
                type="button"
                onClick={() =>
                  setEventDescription(
                    'We are conducting a two-day Web Development Workshop on 14-15 October in Seminar Hall for around 120 students.'
                  )
                }
                className="px-2.5 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded text-[11px] font-medium transition-colors"
              >
                Pre-Event Workshop
              </button>
              <button
                type="button"
                onClick={() =>
                  setEventDescription(
                    'Annual Tech Hackathon on 10-11 November in Computer Centre with estimated budget of Rs. 25,000 for guest honorarium and refreshments.'
                  )
                }
                className="px-2.5 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded text-[11px] font-medium transition-colors"
              >
                Budget & Approval Note
              </button>
              <button
                type="button"
                onClick={() =>
                  setEventDescription(
                    'CodeCraft Coding Competition post-event distribution with 3 student winners receiving cash prizes.'
                  )
                }
                className="px-2.5 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded text-[11px] font-medium transition-colors"
              >
                Post-Event Prize Receipts
              </button>
            </div>

            <div className="pt-2 flex items-center justify-end">
              <button
                type="button"
                disabled={analyzing || !eventDescription.trim()}
                onClick={handleAnalyzeEvent}
                className="inline-flex items-center gap-2 px-5 py-2.5 bg-[#1b365d] hover:bg-[#152a48] disabled:opacity-50 text-white rounded-lg text-xs sm:text-sm font-semibold shadow-sm transition-all"
              >
                {analyzing ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Extracting & Recommending...
                  </>
                ) : (
                  <>
                    <Wand2 className="w-4 h-4 text-amber-300" />
                    Analyze & Recommend Documents
                  </>
                )}
              </button>
            </div>
          </div>

          {/* RECOMMENDATIONS & GROUPED MISSING INFO VIEW */}
          {recommendation && (
            <div className="space-y-6 pt-4 border-t border-slate-200">
              {/* Extracted Context Summary Bar */}
              <div className="bg-blue-50/70 border border-blue-200 rounded-lg p-4 text-xs">
                <div className="font-bold text-[#1b365d] flex items-center gap-2 mb-2">
                  <Info className="w-4 h-4 text-blue-600" />
                  <span>Canonical Parameters Extracted</span>
                  <span className="font-mono bg-blue-100 text-blue-800 text-[10px] px-2 py-0.5 rounded-full uppercase">
                    Stage: {recommendation.detected_stage.replace('_', ' ')}
                  </span>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-slate-700">
                  <div>
                    <span className="text-slate-400 block text-[10px] uppercase font-semibold">Event Name</span>
                    <strong className="text-slate-900">{formInputs.event_name || '—'}</strong>
                  </div>
                  <div>
                    <span className="text-slate-400 block text-[10px] uppercase font-semibold">Dates</span>
                    <strong>{formInputs.dates || formInputs.event_dates || '—'}</strong>
                  </div>
                  <div>
                    <span className="text-slate-400 block text-[10px] uppercase font-semibold">Venue</span>
                    <strong>{formInputs.venue || '—'}</strong>
                  </div>
                  <div>
                    <span className="text-slate-400 block text-[10px] uppercase font-semibold">Participants</span>
                    <strong>{formInputs.expected_participants || '—'}</strong>
                  </div>
                </div>
              </div>

              {/* RECOMMENDED DOCUMENTS CHECKLIST */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                    <Layers className="w-4 h-4 text-[#1b365d]" />
                    Recommended Documents for this Event ({selectedTemplateIds.length} Selected)
                  </h3>
                  <span className="text-xs text-slate-500">
                    Select or uncheck documents to customize package
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {recommendation.templates.map((tmpl: any) => {
                    const isSelected = selectedTemplateIds.includes(tmpl.template_id);
                    return (
                      <div
                        key={tmpl.template_id}
                        onClick={() => toggleTemplateSelection(tmpl.template_id)}
                        className={`p-4 rounded-xl border transition-all cursor-pointer flex items-start gap-3 ${
                          isSelected
                            ? 'bg-blue-50/50 border-[#1b365d] shadow-sm'
                            : 'bg-white border-slate-200 hover:border-slate-300'
                        }`}
                      >
                        <div className="mt-0.5 text-[#1b365d]">
                          {isSelected ? (
                            <CheckSquare className="w-5 h-5 text-[#1b365d]" />
                          ) : (
                            <Square className="w-5 h-5 text-slate-400" />
                          )}
                        </div>

                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-xs sm:text-sm text-slate-900">
                              {tmpl.name}
                            </span>
                            {tmpl.recommended && (
                              <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-100 text-emerald-800 border border-emerald-300">
                                Recommended
                              </span>
                            )}
                            <span className="text-[10px] font-mono px-1.5 py-0.5 bg-slate-100 rounded text-slate-600">
                              {tmpl.numbering_series}
                            </span>
                          </div>
                          <p className="text-xs text-slate-600 mt-1 leading-relaxed">
                            {tmpl.reason}
                          </p>
                          {tmpl.repeat_per && (
                            <div className="mt-2 text-[10px] text-amber-700 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded inline-block font-semibold">
                              Repeats for each item of {tmpl.repeat_per}
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>

                {/* OTHER TEMPLATES (COLLAPSED) */}
                {recommendation.other_templates && recommendation.other_templates.length > 0 && (
                  <div className="pt-2 border-t border-slate-200/60">
                    <button
                      type="button"
                      onClick={() => setShowOtherTemplates((prev) => !prev)}
                      className="text-xs font-semibold text-slate-600 hover:text-slate-900 flex items-center gap-1.5 py-1.5 px-2.5 rounded-lg bg-slate-50 hover:bg-slate-100 transition-colors border border-slate-200"
                    >
                      <ChevronRight className={`w-3.5 h-3.5 transition-transform ${showOtherTemplates ? 'rotate-90' : ''}`} />
                      Other Templates ({recommendation.other_templates.length})
                    </button>
                    {showOtherTemplates && (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3">
                        {recommendation.other_templates.map((tmpl: any) => {
                          const isSelected = selectedTemplateIds.includes(tmpl.template_id);
                          return (
                            <div
                              key={tmpl.template_id}
                              onClick={() => toggleTemplateSelection(tmpl.template_id)}
                              className={`p-4 rounded-xl border transition-all cursor-pointer flex items-start gap-3 ${
                                isSelected
                                  ? 'bg-blue-50/50 border-[#1b365d] shadow-sm'
                                  : 'bg-white border-slate-200 hover:border-slate-300'
                              }`}
                            >
                              <div className="mt-0.5 text-[#1b365d]">
                                {isSelected ? (
                                  <CheckSquare className="w-5 h-5 text-[#1b365d]" />
                                ) : (
                                  <Square className="w-5 h-5 text-slate-400" />
                                )}
                              </div>
                              <div className="flex-1">
                                <div className="flex items-center gap-2">
                                  <span className="font-bold text-xs sm:text-sm text-slate-900">
                                    {tmpl.name}
                                  </span>
                                  <span className="text-[10px] font-mono px-1.5 py-0.5 bg-slate-100 rounded text-slate-600">
                                    {tmpl.numbering_series}
                                  </span>
                                </div>
                                <p className="text-xs text-slate-600 mt-1 leading-relaxed">
                                  {tmpl.reason}
                                </p>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* GROUPED MISSING-INFO PANEL */}
              {recommendation.grouped_missing_fields && recommendation.grouped_missing_fields.length > 0 && (
                <div className="bg-amber-50/50 border border-amber-200 rounded-xl p-5 space-y-4">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-amber-200/80 pb-3 gap-2">
                    <div>
                      <h4 className="text-xs font-bold uppercase tracking-wider text-amber-900 flex items-center gap-2">
                        <HelpCircle className="w-4 h-4 text-amber-700" />
                        Grouped Missing Information ({recommendation.grouped_missing_fields.length})
                      </h4>
                      <p className="text-xs text-amber-800 mt-0.5">
                        Shared fields are entered once and automatically propagated to every selected document.
                      </p>
                    </div>

                    {hasUnacceptedAiDraft && (
                      <button
                        type="button"
                        onClick={handleAcceptAllAiDrafts}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-bold shadow-2xs transition-colors self-start sm:self-center"
                      >
                        <CheckCircle className="w-3.5 h-3.5" />
                        Accept All AI Drafts
                      </button>
                    )}
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    {recommendation.grouped_missing_fields.map((field: any) => {
                      if (field.key === 'winners' || field.key === 'bills') {
                        return null; // Handled in dedicated sections below
                      }

                      if (field.key === 'dates_confirmation') {
                        return (
                          <div
                            key={field.key}
                            className="space-y-2 bg-amber-50 p-4 rounded-lg border border-amber-300 shadow-2xs col-span-1 sm:col-span-2"
                          >
                            <div className="flex items-center justify-between gap-2">
                              <label className="text-xs font-bold text-amber-950 flex items-center gap-1.5">
                                <Calendar className="w-4 h-4 text-amber-700" />
                                {field.label}
                              </label>
                              <span className="text-[10px] font-bold text-amber-800 bg-amber-100 px-2 py-0.5 rounded border border-amber-300">
                                Confirmation Required
                              </span>
                            </div>
                            <p className="text-xs font-semibold text-amber-900">
                              {field.ask}
                            </p>
                            <label className="flex items-center gap-2 text-xs font-bold text-amber-950 cursor-pointer pt-1">
                              <input
                                type="checkbox"
                                checked={datesConfirmed}
                                onChange={(e) => setDatesConfirmed(e.target.checked)}
                                className="w-4 h-4 text-[#1b365d] rounded border-amber-400 focus:ring-[#1b365d]"
                              />
                              <span>Confirm inferred event year</span>
                            </label>
                          </div>
                        );
                      }

                      const fieldVal = formInputs[field.key] || '';
                      const isAiDraft = typeof fieldVal === 'string' && fieldVal.includes('[AI-drafted');
                      const isEmptyRequired = !field.defer_ok && (fieldVal === undefined || fieldVal === null || String(fieldVal).trim() === '');

                      return (
                        <div key={field.key} className={`space-y-1.5 bg-white p-3.5 rounded-lg border shadow-2xs ${isEmptyRequired ? 'border-amber-300 ring-1 ring-amber-200' : 'border-amber-200/60'}`}>
                          <div className="flex items-center justify-between gap-2">
                            <label className="text-xs font-bold text-slate-800 flex items-center gap-1.5">
                              <span>{field.label}</span>
                              {isEmptyRequired && (
                                <span className="text-[9px] font-bold text-amber-700 bg-amber-100 px-1.5 py-0.2 rounded">
                                  Required
                                </span>
                              )}
                            </label>
                            {field.defer_ok && (
                              <span className="text-[10px] font-semibold text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded border border-slate-200">
                                Optional / Defer OK
                              </span>
                            )}
                          </div>
                          <p className="text-[11px] text-slate-500 italic">
                            {field.ask}
                          </p>

                          {field.key === 'description' || field.key === 'objectives' ? (
                            <textarea
                              rows={3}
                              value={fieldVal}
                              onChange={(e) =>
                                setFormInputs({
                                  ...formInputs,
                                  [field.key]: e.target.value,
                                })
                              }
                              placeholder={`Enter ${field.label.toLowerCase()}...`}
                              className={`w-full border ${isEmptyRequired ? 'border-amber-400' : 'border-slate-300'} rounded-md py-1.5 px-3 text-xs focus:ring-2 focus:ring-[#1b365d] focus:outline-none`}
                            />
                          ) : (
                            <input
                              type={field.type === 'number' ? 'number' : field.type === 'date' ? 'date' : 'text'}
                              value={fieldVal}
                              onChange={(e) =>
                                setFormInputs({
                                  ...formInputs,
                                  [field.key]: e.target.value,
                                })
                              }
                              placeholder={`Enter ${field.label.toLowerCase()}...`}
                              className={`w-full border ${isEmptyRequired ? 'border-amber-400' : 'border-slate-300'} rounded-md py-1.5 px-3 text-xs focus:ring-2 focus:ring-[#1b365d] focus:outline-none`}
                            />
                          )}

                          {isAiDraft && (
                            <div className="flex items-center justify-between bg-amber-50 border border-amber-300 px-2 py-1 rounded text-[11px] text-amber-900 mt-1">
                              <span className="font-medium">AI-drafted value requires review:</span>
                              <button
                                type="button"
                                onClick={() => handleAcceptAiDraft(field.key)}
                                className="inline-flex items-center gap-1 bg-emerald-600 hover:bg-emerald-700 text-white px-2 py-0.5 rounded text-[10px] font-bold shadow-xs transition-colors"
                              >
                                <CheckCircle className="w-3 h-3" />
                                Accept
                              </button>
                            </div>
                          )}

                          <div className="flex flex-wrap items-center gap-1 mt-1">
                            <span className="text-[10px] text-slate-400">Needed by:</span>
                            {field.needed_by.map((docName: string) => (
                              <span
                                key={docName}
                                className="text-[10px] font-semibold bg-slate-100 text-slate-700 px-1.5 py-0.2 rounded"
                              >
                                {docName}
                              </span>
                            ))}
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  {/* Winners Sub-Editor if Prize Receipts selected */}
                  {selectedTemplateIds.some((id) =>
                    recommendation.templates.some((t: any) => t.template_id === id && (t.slug === 'prize_money_receipt' || t.repeat_per === 'winners'))
                  ) && (
                    <div className="bg-white rounded-lg p-4 border border-amber-200 space-y-3">
                      <div className="flex items-center justify-between">
                        <div className="text-xs font-bold text-slate-900">
                          Winners List (1 Receipt will be generated per winner)
                        </div>
                        <button
                          type="button"
                          onClick={() =>
                            setWinners([
                              ...winners,
                              { name: '', roll_no: '', amount: 1000, position: `${winners.length + 1}th Place` },
                            ])
                          }
                          className="inline-flex items-center gap-1 text-[11px] font-semibold bg-blue-50 text-[#1b365d] px-2.5 py-1 rounded hover:bg-blue-100"
                        >
                          <Plus className="w-3 h-3" />
                          Add Winner
                        </button>
                      </div>

                      <div className="space-y-2">
                        {winners.map((w, idx) => (
                          <div key={idx} className="grid grid-cols-12 gap-2 items-center text-xs">
                            <input
                              type="text"
                              placeholder="Winner Full Name"
                              value={w.name}
                              onChange={(e) => {
                                const copy = [...winners];
                                copy[idx].name = e.target.value;
                                setWinners(copy);
                              }}
                              className="col-span-4 border border-slate-300 rounded p-1.5"
                            />
                            <input
                              type="text"
                              placeholder="Roll / Admission No"
                              value={w.roll_no}
                              onChange={(e) => {
                                const copy = [...winners];
                                copy[idx].roll_no = e.target.value;
                                setWinners(copy);
                              }}
                              className="col-span-3 border border-slate-300 rounded p-1.5 font-mono"
                            />
                            <input
                              type="number"
                              placeholder="Prize Amount (Rs)"
                              value={w.amount}
                              onChange={(e) => {
                                const copy = [...winners];
                                copy[idx].amount = Number(e.target.value);
                                setWinners(copy);
                              }}
                              className="col-span-3 border border-slate-300 rounded p-1.5"
                            />
                            <div className="col-span-2 text-right">
                              {winners.length > 1 && (
                                <button
                                  type="button"
                                  onClick={() => setWinners(winners.filter((_, i) => i !== idx))}
                                  className="text-red-500 hover:text-red-700 p-1"
                                >
                                  <Trash2 className="w-4 h-4" />
                                </button>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Bills Sub-Editor if Bill Certificate selected */}
                  {selectedTemplateIds.some((id) =>
                    recommendation.templates.some((t: any) => t.template_id === id && (t.slug === 'bill_certificate' || t.repeat_per === 'bills'))
                  ) && (
                    <div className="bg-white rounded-lg p-4 border border-amber-200 space-y-3">
                      <div className="flex items-center justify-between">
                        <div className="text-xs font-bold text-slate-900">
                          Bills / Expenses List (1 Certificate will be generated per bill)
                        </div>
                        <button
                          type="button"
                          onClick={() =>
                            setBills([
                              ...bills,
                              { bill_no: `INV-${bills.length + 101}`, vendor: '', amount: 1000, particulars: 'Supplies' },
                            ])
                          }
                          className="inline-flex items-center gap-1 text-[11px] font-semibold bg-blue-50 text-[#1b365d] px-2.5 py-1 rounded hover:bg-blue-100"
                        >
                          <Plus className="w-3 h-3" />
                          Add Bill
                        </button>
                      </div>

                      <div className="space-y-2">
                        {bills.map((b, idx) => (
                          <div key={idx} className="grid grid-cols-12 gap-2 items-center text-xs">
                            <input
                              type="text"
                              placeholder="Bill / Invoice No"
                              value={b.bill_no}
                              onChange={(e) => {
                                const copy = [...bills];
                                copy[idx].bill_no = e.target.value;
                                setBills(copy);
                              }}
                              className="col-span-3 border border-slate-300 rounded p-1.5 font-mono"
                            />
                            <input
                              type="text"
                              placeholder="Vendor Name"
                              value={b.vendor}
                              onChange={(e) => {
                                const copy = [...bills];
                                copy[idx].vendor = e.target.value;
                                setBills(copy);
                              }}
                              className="col-span-4 border border-slate-300 rounded p-1.5"
                            />
                            <input
                              type="number"
                              placeholder="Amount (Rs)"
                              value={b.amount}
                              onChange={(e) => {
                                const copy = [...bills];
                                copy[idx].amount = Number(e.target.value);
                                setBills(copy);
                              }}
                              className="col-span-3 border border-slate-300 rounded p-1.5"
                            />
                            <div className="col-span-2 text-right">
                              {bills.length > 1 && (
                                <button
                                  type="button"
                                  onClick={() => setBills(bills.filter((_, i) => i !== idx))}
                                  className="text-red-500 hover:text-red-700 p-1"
                                >
                                  <Trash2 className="w-4 h-4" />
                                </button>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* REFERENCE NUMBERS PANEL */}
              <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center gap-2">
                    <FileText className="w-4 h-4 text-slate-600" />
                    Reference Numbers To Be Reserved
                  </h4>
                  <span className="text-[11px] text-slate-500">
                    Allocated on generate
                  </span>
                </div>

                <div className="space-y-1.5">
                  {selectedTemplateIds.map((id) => {
                    const tmpl = recommendation.templates.find((t: any) => t.template_id === id);
                    if (!tmpl) return null;
                    const series = tmpl.numbering_series || 'DOC';
                    return (
                      <div
                        key={id}
                        className="text-xs text-slate-700 flex flex-col sm:flex-row sm:items-center justify-between font-mono bg-white px-3 py-2 rounded border border-slate-200 gap-1"
                      >
                        <span className="font-sans font-medium text-slate-900">{tmpl.name}:</span>
                        <span className="text-[#1b365d] font-bold">
                          Numbers to be reserved on generate: ACM/26-27/{series}/001 (suggested)
                        </span>
                      </div>
                    );
                  })}
                </div>

                <label className="flex items-center gap-2.5 text-xs font-bold text-slate-900 cursor-pointer pt-2 border-t border-slate-200">
                  <input
                    type="checkbox"
                    checked={numberingConfirmed}
                    onChange={(e) => setNumberingConfirmed(e.target.checked)}
                    className="w-4 h-4 text-[#1b365d] rounded border-slate-300 focus:ring-[#1b365d]"
                  />
                  <span>Confirm reference numbers to be reserved on generate</span>
                </label>
              </div>

              {/* GENERATE BATCH BUTTON */}
              <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-4 border-t border-slate-200">
                <div className="text-xs space-y-1">
                  <div className="text-slate-500">
                    Ready to reserve serial numbers and render {selectedTemplateIds.length} document type(s).
                  </div>
                  {emptyRequiredFields.length > 0 && (
                    <div className="text-amber-800 font-semibold flex items-center gap-1">
                      <AlertCircle className="w-3.5 h-3.5 text-amber-600 flex-shrink-0" />
                      Generate disabled: Fill required field(s): {emptyRequiredFields.map((f: any) => f.label).join(', ')}.
                    </div>
                  )}
                  {hasUnacceptedAiDraft && (
                    <div className="text-red-600 font-semibold flex items-center gap-1">
                      <AlertCircle className="w-3.5 h-3.5" />
                      Generate disabled: Review and accept all AI-drafted fields above.
                    </div>
                  )}
                  {!numberingConfirmed && (
                    <div className="text-amber-700 font-semibold flex items-center gap-1">
                      <AlertCircle className="w-3.5 h-3.5" />
                      Generate disabled: Check the box to confirm reference numbers above.
                    </div>
                  )}
                  {recommendation?.extracted_data?.dates_inferred && !datesConfirmed && (
                    <div className="text-amber-700 font-semibold flex items-center gap-1">
                      <AlertCircle className="w-3.5 h-3.5" />
                      Generate disabled: Confirm the inferred event year above.
                    </div>
                  )}
                </div>

                <button
                  type="button"
                  disabled={
                    generatingBatch ||
                    selectedTemplateIds.length === 0 ||
                    !numberingConfirmed ||
                    hasUnacceptedAiDraft ||
                    (Boolean(recommendation?.extracted_data?.dates_inferred) && !datesConfirmed) ||
                    emptyRequiredFields.length > 0
                  }
                  onClick={handleGenerateBatch}
                  className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-3 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white rounded-lg text-sm font-bold shadow-md transition-all"
                >
                  {generatingBatch ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Generating Batch Package...
                    </>
                  ) : (
                    <>
                      <FolderArchive className="w-4 h-4" />
                      Generate Selected Documents ({selectedTemplateIds.length})
                    </>
                  )}
                </button>
              </div>

              {/* PROGRESS BAR */}
              {generatingBatch && batchProgress && (
                <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg flex items-center gap-3">
                  <Loader2 className="w-5 h-5 text-[#1b365d] animate-spin flex-shrink-0" />
                  <span className="text-xs font-semibold text-[#1b365d]">{batchProgress}</span>
                </div>
              )}

              {/* BATCH GENERATION RESULT CARD */}
              {batchResult && (
                <div className="bg-emerald-50 border-2 border-emerald-300 rounded-xl p-6 space-y-4">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                        <h4 className="text-base font-bold text-emerald-950">
                          Batch Generation Complete ({batchResult.documents_count} Documents)
                        </h4>
                      </div>
                      <p className="text-xs text-emerald-800 mt-1">
                        All official documents have been compiled, assigned unique reference numbers, and rendered to PDF.
                      </p>
                    </div>

                    <a
                      href={batchResult.zip_url}
                      download
                      className="inline-flex items-center gap-2 bg-emerald-700 hover:bg-emerald-800 text-white px-5 py-2.5 rounded-lg text-xs sm:text-sm font-bold shadow transition-colors"
                    >
                      <Download className="w-4 h-4" />
                      Download Complete ZIP ({batchResult.zip_filename})
                    </a>
                  </div>

                  {/* List of generated items */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 pt-2">
                    {batchResult.documents.map((doc: any) => (
                      <div
                        key={doc.id}
                        className="bg-white p-3.5 rounded-lg border border-emerald-200 shadow-2xs flex flex-col justify-between"
                      >
                        <div>
                          <div className="font-bold text-xs text-slate-900 truncate">
                            {doc.title}
                          </div>
                          <div className="font-mono text-[11px] font-semibold text-amber-900 bg-amber-50 border border-amber-200 px-1.5 py-0.5 rounded mt-1 inline-block">
                            {doc.ref_no}
                          </div>
                        </div>

                        <div className="mt-3 pt-2 border-t border-slate-100 flex items-center justify-between text-xs">
                          <button
                            type="button"
                            onClick={() => handleViewDoc(doc.id)}
                            className="text-[#1b365d] font-bold hover:underline"
                          >
                            Review →
                          </button>

                          <a
                            href={`/api/v1/clubs/${clubId}/documents/${doc.id}/download?format=pdf`}
                            download
                            className="text-red-600 hover:text-red-800 font-semibold flex items-center gap-1"
                          >
                            <Download className="w-3 h-3" /> PDF
                          </a>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* SECTION 2: EXISTING EVENTS & PACKAGES */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
            <Calendar className="w-5 h-5 text-[#1b365d]" />
            Active Campus Events ({events.length})
          </h3>
          <button
            onClick={fetchEvents}
            className="inline-flex items-center gap-1.5 text-xs text-slate-600 bg-white hover:bg-slate-50 border border-slate-200 px-3 py-1.5 rounded-lg font-semibold transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        {events.length === 0 ? (
          <div className="bg-white rounded-xl border border-slate-200 p-12 text-center shadow-sm">
            <Calendar className="w-10 h-10 text-slate-300 mx-auto mb-2" />
            <h3 className="text-base font-bold text-slate-800">No Events Created Yet</h3>
            <p className="text-xs text-slate-500 mt-1 max-w-md mx-auto">
              Use the "Describe Your Event" box above to plan your first event and batch generate required documents.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {events.map((ev) => (
              <div
                key={ev.id}
                className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 space-y-4 hover:border-slate-300 transition-all"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-4">
                  <div>
                    <div className="flex items-center gap-2.5">
                      <h3 className="text-lg font-bold text-slate-900">{ev.title}</h3>
                      {ev.event_code && (
                        <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200">
                          {ev.event_code}
                        </span>
                      )}
                      <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300">
                        {ev.status}
                      </span>
                    </div>
                    <p className="text-xs text-slate-500 mt-1 flex items-center gap-2">
                      <span>Venue: <strong>{ev.record?.venue || '—'}</strong></span>
                      <span>•</span>
                      <span>Date: <strong>{ev.record?.document_date || ev.record?.dates || '—'}</strong></span>
                      <span>•</span>
                      <span>Participants: <strong>{ev.record?.expected_participants || '—'}</strong></span>
                    </p>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => handleOpenNewDocModal(ev)}
                      className="inline-flex items-center gap-1.5 text-xs font-semibold bg-[#1b365d] hover:bg-[#152a48] text-white px-3 py-1.5 rounded-lg transition-colors shadow-xs"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      + New Document
                    </button>
                    <button
                      type="button"
                      onClick={() => handleOpenEdit(ev)}
                      className="inline-flex items-center gap-1.5 text-xs font-semibold bg-slate-100 hover:bg-slate-200 text-slate-700 px-3 py-1.5 rounded-lg transition-colors"
                    >
                      <Edit2 className="w-3.5 h-3.5 text-slate-500" />
                      Edit Event
                    </button>
                  </div>
                </div>

                {/* Linked Documents List */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-xs font-bold text-slate-700">
                    <span className="flex items-center gap-1.5">
                      <FileText className="w-4 h-4 text-amber-600" />
                      Generated Documents ({ev.documents?.length || 0})
                    </span>
                  </div>

                  {ev.documents && ev.documents.length > 0 ? (
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 pt-1">
                      {ev.documents.map((doc: any) => (
                        <div
                          key={doc.id}
                          onClick={() => handleViewDoc(doc.id)}
                          className="p-3 bg-slate-50/70 hover:bg-blue-50/40 rounded-lg border border-slate-200 hover:border-[#1b365d] transition-all cursor-pointer flex flex-col justify-between"
                        >
                          <div>
                            <div className="flex items-center justify-between mb-1">
                              <span className="text-xs font-bold text-slate-900 capitalize truncate">
                                {doc.template_slug.replace(/_/g, ' ')}
                              </span>
                              <span data-testid={`doc-version-${doc.id}`} className="text-[10px] font-mono text-slate-500">
                                v{doc.current_version_no}
                              </span>
                            </div>
                            <p className="text-[11px] font-mono font-medium text-amber-800">
                              {doc.ref_no || 'No ref number'}
                            </p>
                          </div>
                          <div className="mt-2 pt-2 border-t border-slate-200/60 flex items-center justify-between text-[10px] text-slate-500">
                            <span>{doc.status}</span>
                            <span className="text-[#1b365d] font-bold">Review →</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-3 bg-slate-50 border border-dashed border-slate-200 rounded-lg">
                      <p className="text-xs text-slate-500 italic">
                        No documents generated under this event yet.
                      </p>
                      <button
                        type="button"
                        onClick={() => handleOpenNewDocModal(ev)}
                        className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#1b365d] hover:underline"
                      >
                        <Plus className="w-3.5 h-3.5" />
                        Generate first document for this event →
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Edit Event Modal */}
      {editingEvent && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl shadow-xl border border-slate-200 max-w-lg w-full p-6 space-y-4">
            <h3 className="text-lg font-bold text-slate-900">Edit Event Canonical Record</h3>
            <form onSubmit={handleSaveEdit} className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase mb-1">Title</label>
                <input
                  type="text"
                  value={editTitle}
                  onChange={(e) => setEditTitle(e.target.value)}
                  className="w-full border border-slate-300 rounded-lg p-2 text-sm focus:ring-2 focus:ring-[#1b365d] focus:outline-none"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase mb-1">Event Code</label>
                <input
                  type="text"
                  value={editEventCode}
                  onChange={(e) => setEditEventCode(e.target.value)}
                  className="w-full border border-slate-300 rounded-lg p-2 text-sm focus:ring-2 focus:ring-[#1b365d] focus:outline-none font-mono"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase mb-1">Event Venue</label>
                <input
                  type="text"
                  value={editVenue}
                  onChange={(e) => setEditVenue(e.target.value)}
                  className="w-full border border-slate-300 rounded-lg p-2 text-sm focus:ring-2 focus:ring-[#1b365d] focus:outline-none"
                />
              </div>

              <div className="flex items-center gap-2 p-3 bg-blue-50/60 border border-blue-200 rounded-lg text-xs text-blue-900">
                <input
                  type="checkbox"
                  id="cascadeDocs"
                  checked={updateDocuments}
                  onChange={(e) => setUpdateDocuments(e.target.checked)}
                  className="rounded text-[#1b365d] focus:ring-[#1b365d]"
                />
                <label htmlFor="cascadeDocs" className="cursor-pointer font-medium">
                  Re-render and increment version numbers of all linked documents automatically
                </label>
              </div>

              <div className="flex items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setEditingEvent(null)}
                  className="px-4 py-2 border border-slate-300 text-slate-700 rounded-lg text-xs font-semibold hover:bg-slate-50 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="px-5 py-2 bg-[#1b365d] hover:bg-[#152a48] text-white rounded-lg text-xs font-semibold transition-colors disabled:opacity-50"
                >
                  {saving ? 'Updating...' : 'Save & Cascade'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* New Document Template Picker Modal */}
      {newDocModalEvent && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl shadow-xl border border-slate-200 max-w-xl w-full p-6 space-y-4 max-h-[90vh] flex flex-col">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div>
                <h3 className="text-base font-bold text-slate-900">
                  New Document for: {newDocModalEvent.title}
                </h3>
                <p className="text-xs text-slate-500">
                  Choose a template to generate a document linked to this event.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setNewDocModalEvent(null)}
                className="text-slate-400 hover:text-slate-600 text-lg leading-none p-1"
              >
                ✕
              </button>
            </div>

            <div className="flex-1 overflow-y-auto space-y-2 py-2">
              {loadingTemplates ? (
                <div className="py-8 flex flex-col items-center justify-center text-slate-400 gap-2">
                  <Loader2 className="w-6 h-6 animate-spin text-[#1b365d]" />
                  <span className="text-xs">Loading available templates...</span>
                </div>
              ) : availableTemplates.length === 0 ? (
                <div className="py-8 text-center text-slate-400 text-xs">
                  No published templates available for this club.
                </div>
              ) : (
                <div className="grid grid-cols-1 gap-2.5">
                  {availableTemplates.map((t: any) => (
                    <div
                      key={t.id}
                      className="p-3.5 rounded-lg border border-slate-200 hover:border-[#1b365d] hover:bg-slate-50/70 transition-all flex items-center justify-between gap-3"
                    >
                      <div>
                        <h4 className="text-xs font-bold text-slate-900">{t.name}</h4>
                        {t.description && (
                          <p className="text-[11px] text-slate-500 line-clamp-2 mt-0.5">
                            {t.description}
                          </p>
                        )}
                        <span className="inline-block mt-1 text-[10px] font-mono text-slate-400">
                          {t.slug}
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleSelectTemplateForEvent(t.id)}
                        className="shrink-0 px-3 py-1.5 bg-[#1b365d] hover:bg-[#152a48] text-white rounded-lg text-xs font-semibold transition-colors cursor-pointer"
                      >
                        Select →
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="flex justify-end pt-2 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setNewDocModalEvent(null)}
                className="px-4 py-2 border border-slate-300 text-slate-700 rounded-lg text-xs font-semibold hover:bg-slate-50 transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
