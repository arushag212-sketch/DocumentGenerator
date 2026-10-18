import React, { useState, useEffect } from 'react';
import {
  FileText,
  ArrowLeft,
  Sparkles,
  AlertTriangle,
  CheckCircle2,
  Building,
  Hash,
  Loader2,
  Check,
  Info,
} from 'lucide-react';
import { api } from '../api/client';
import { TemplateDetail, GeneratedDocument } from '../types';

interface NewDocumentPageProps {
  clubId: string | number;
  templateId: string;
  eventId?: string | null;
  onCancel: () => void;
  onGenerated: (doc: GeneratedDocument) => void;
}

export const NewDocumentPage: React.FC<NewDocumentPageProps> = ({
  clubId,
  templateId,
  eventId,
  onCancel,
  onGenerated,
}) => {
  const [template, setTemplate] = useState<TemplateDetail | null>(null);
  const [linkedEvent, setLinkedEvent] = useState<any | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [generating, setGenerating] = useState<boolean>(false);
  const [extracting, setExtracting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Natural Language Description
  const [eventDescription, setEventDescription] = useState<string>('');

  // Form Field State
  const [formData, setFormData] = useState<Record<string, any>>({});
  const [fieldProvenance, setFieldProvenance] = useState<Record<string, { source: string; confirmed: boolean }>>({});
  const [deferredFields, setDeferredFields] = useState<Record<string, boolean>>({});
  const [refNoConfirmed, setRefNoConfirmed] = useState<boolean>(false);
  const [reservationId, setReservationId] = useState<string | null>(null);
  const [reserving, setReserving] = useState<boolean>(false);

  // Load template schema & defaults
  useEffect(() => {
    const loadSchema = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await api.documents.getTemplateSchema(clubId, templateId);
        setTemplate(data);

        // Populate initial defaults
        const initialForm: Record<string, any> = {};
        data.fields.forEach((f) => {
          if (data.defaults[f.key] !== undefined && data.defaults[f.key] !== null) {
            initialForm[f.key] = data.defaults[f.key];
          } else if (f.default_value !== undefined && f.default_value !== null) {
            initialForm[f.key] = f.default_value;
          } else if (f.type === 'enum' || (f.values && f.values.length > 0)) {
            initialForm[f.key] = (f.values && f.values.length > 0) ? f.values[0] : 'Offline';
          }
        });

        // Add live club defaults (only document_date defaults)
        if (data.defaults.document_date) initialForm.document_date = data.defaults.document_date;
        if (data.defaults.suggested_ref_no) initialForm.ref_no = data.defaults.suggested_ref_no;

        // If eventId provided, load event and prefill canonical fields
        if (eventId) {
          try {
            const ev = await api.events.get(clubId, eventId);
            if (ev) {
              setLinkedEvent(ev);
              if (ev.title) initialForm.event_name = ev.title;
              if (ev.event_code) initialForm.event_code = ev.event_code;
              if (ev.record) {
                Object.entries(ev.record).forEach(([k, v]) => {
                  if (v !== undefined && v !== null && v !== '') {
                    initialForm[k] = v;
                  }
                });
              }
            }
          } catch {
            // fallback gracefully
          }
        }

        setFormData(initialForm);
      } catch (err: any) {
        setError(err.message || 'Failed to load template schema');
      } finally {
        setLoading(false);
      }
    };
    loadSchema();
  }, [clubId, templateId, eventId]);

  // Handle Natural Language Extraction
  const handleExtract = async () => {
    if (!eventDescription.trim() || eventDescription.length < 5) {
      alert('Please enter a descriptive prompt about your event first.');
      return;
    }

    try {
      setExtracting(true);
      setError(null);
      const res = await api.documents.extract(clubId, eventDescription);

      const updated = { ...formData };
      const prov = { ...fieldProvenance };

      Object.entries(res.extracted_data).forEach(([k, v]) => {
        if (v !== null && v !== undefined && v !== '') {
          updated[k] = v;
          const isAiDraft = k === 'description' || k === 'objectives' || (typeof v === 'string' && v.includes('[AI-drafted'));
          prov[k] = { source: isAiDraft ? 'extracted_llm' : 'extracted_rule', confirmed: !isAiDraft };
        }
      });

      setFormData(updated);
      setFieldProvenance(prov);
    } catch (err: any) {
      alert(`Extraction error: ${err.message}`);
    } finally {
      setExtracting(false);
    }
  };

  const handleFieldChange = (key: string, value: any) => {
    setFormData((prev) => ({ ...prev, [key]: value }));
    // If user edited an AI-drafted field, mark as confirmed by user
    if (fieldProvenance[key]) {
      setFieldProvenance((prev) => ({
        ...prev,
        [key]: { source: 'user', confirmed: true },
      }));
    }
  };

  const confirmField = (key: string) => {
    if (fieldProvenance[key]) {
      setFieldProvenance((prev) => ({
        ...prev,
        [key]: { ...prev[key], confirmed: true },
      }));
    }
    if (formData[key] && typeof formData[key] === 'string') {
      const cleaned = formData[key].replace(/^\[AI-drafted,\s*review\]\s*/i, '');
      setFormData((prev) => ({ ...prev, [key]: cleaned }));
    }
  };

  const handleConfirmRefNo = async () => {
    try {
      setReserving(true);
      setError(null);
      const seriesKey = template?.numbering_series || template?.id || formData.event_code || 'ROOM';
      const res = await api.documents.reserveNumber(clubId, seriesKey, {
        template_id: templateId,
        event_code: formData.event_code,
      });
      setReservationId(res.reservation_id);
      setFormData((prev) => ({ ...prev, ref_no: res.ref_no }));
      setRefNoConfirmed(true);
    } catch (err: any) {
      setError(`Failed to reserve reference number: ${err.message}`);
    } finally {
      setReserving(false);
    }
  };

  // Missing required fields detection
  const requiredFields = template?.fields.filter((f) => f.required) || [];
  const missingFields = requiredFields.filter((f) => {
    const val = formData[f.key];
    const isFilled = val !== undefined && val !== null && String(val).trim() !== '';
    const isDeferred = Boolean(f.defer_ok && deferredFields[f.key]);
    return !isFilled && !isDeferred;
  });

  const unconfirmedDrafts = Object.entries(fieldProvenance).filter(
    ([_, p]) => !p.confirmed
  );

  const isRefConfirmNeeded = Boolean(
    (template?.numbering_series || template?.confirm_numbering) &&
    !reservationId
  );

  const canGenerate = missingFields.length === 0 && unconfirmedDrafts.length === 0 && !isRefConfirmNeeded;

  const getGenerateButtonHint = () => {
    if (generating) return 'Rendering via LibreOffice...';
    if (unconfirmedDrafts.length > 0) return 'Review and accept all AI drafts to generate';
    if (missingFields.length > 0) return `Missing ${missingFields.length} required field(s)`;
    if (isRefConfirmNeeded) return 'Please reserve a Reference Number before generating';
    return 'Generate official document';
  };

  // Generate Document
  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canGenerate) return;

    try {
      setGenerating(true);
      setError(null);

      const confirmedKeys = Object.keys(formData).filter((k) => !fieldProvenance[k] || fieldProvenance[k].confirmed);

      const deferredKeys = Object.keys(deferredFields).filter((k) => deferredFields[k]);

      const res = await api.documents.generate(clubId, {
        template_id: templateId,
        event_id: eventId || undefined,
        title: formData.event_name,
        ref_no: formData.ref_no,
        ref_no_confirmed: refNoConfirmed,
        reservation_id: reservationId || undefined,
        event_data: formData,
        confirmed_fields: confirmedKeys,
        deferred_fields: deferredKeys,
      });

      onGenerated(res);
    } catch (err: any) {
      setError(err.message || 'Failed to generate document');
    } finally {
      setGenerating(false);
    }
  };

  if (loading) {
    return (
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-12 text-center">
        <Loader2 className="w-8 h-8 text-[#1b365d] animate-spin mx-auto mb-3" />
        <p className="text-slate-600 text-sm font-medium">Loading official template schema...</p>
      </div>
    );
  }

  if (error && !template) {
    return (
      <div className="bg-white rounded-xl shadow-sm border border-red-200 p-8 text-center">
        <AlertTriangle className="w-8 h-8 text-red-500 mx-auto mb-2" />
        <h3 className="text-lg font-bold text-slate-800">Error Loading Template</h3>
        <p className="text-sm text-red-600 mt-1">{error}</p>
        <button
          onClick={onCancel}
          className="mt-4 px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-sm font-semibold rounded-lg"
        >
          Back to Dashboard
        </button>
      </div>
    );
  }

  const formatAskLabel = (f: { ask?: string; key: string }) => {
    let lbl = f.ask || f.key.replace(/_/g, ' ');
    const ay = template?.defaults?.academic_year || '2026-27';
    lbl = lbl.replace('{academic_year}', ay).replace('{next}', '001');
    return lbl;
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <button
            onClick={onCancel}
            type="button"
            className="inline-flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-800 font-semibold mb-2"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            Back to Dashboard
          </button>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-slate-900">{template?.name}</h1>
            <span className="bg-blue-50 text-[#1b365d] text-xs px-2.5 py-0.5 rounded-full font-semibold border border-blue-200 uppercase tracking-wider">
              {template?.stage.replace('_', ' ')}
            </span>
          </div>
          <p className="text-xs text-slate-600 mt-1">{template?.description}</p>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500 font-mono bg-slate-100 px-2 py-1 rounded border border-slate-200">
            LibreOffice PDF Converter
          </span>
        </div>
      </div>

      {linkedEvent && (
        <div className="p-4 bg-blue-50 border border-blue-200 rounded-xl text-xs sm:text-sm text-blue-900 flex items-center justify-between gap-3 shadow-2xs">
          <div className="flex items-center gap-2.5">
            <Info className="w-5 h-5 text-blue-600 flex-shrink-0" />
            <div>
              <span className="font-bold">Generating document for Event: </span>
              <span className="font-semibold text-slate-900">{linkedEvent.title}</span>
              <p className="text-[11px] text-blue-700 mt-0.5">
                Canonical venue, dates, and event code have been pre-filled from this event's shared context.
              </p>
            </div>
          </div>
          <span className="font-mono text-[10px] bg-blue-100 text-blue-800 px-2 py-1 rounded font-bold uppercase tracking-wider">
            Linked Event
          </span>
        </div>
      )}

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* 2-Column Layout: Form & Missing-Info Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Column: Describe Your Event & Dynamic Form */}
        <div className="lg:col-span-2 space-y-6">
          {/* AI Event Extractor Box */}
          <div className="bg-gradient-to-r from-amber-50/60 to-blue-50/60 rounded-xl border border-amber-200/80 p-5 shadow-sm">
            <div className="flex items-center gap-2 text-amber-900 font-bold text-sm mb-2">
              <Sparkles className="w-4 h-4 text-amber-600" />
              <span>Describe Your Event (AI Pre-fill)</span>
            </div>
            <p className="text-xs text-slate-600 mb-3">
              Type or paste your event description, dates, times, and venue in natural language. Our NLP extractor will populate the form fields below for your review.
            </p>
            <textarea
              rows={3}
              value={eventDescription}
              onChange={(e) => setEventDescription(e.target.value)}
              placeholder="e.g., We are organizing Smart India Hackathon 2026 Internal Hackathon on 15/10/2026 from 09:00 AM to 06:00 PM at Seminar Hall. Expected participants: 120 students."
              className="w-full text-xs sm:text-sm p-3 rounded-lg border border-slate-300 focus:ring-2 focus:ring-[#1b365d] focus:border-transparent bg-white shadow-inner"
            />
            <div className="mt-2.5 flex justify-end">
              <button
                type="button"
                onClick={handleExtract}
                disabled={extracting}
                className="inline-flex items-center gap-2 bg-[#1b365d] hover:bg-[#152a48] text-white px-4 py-2 rounded-lg text-xs font-semibold shadow-sm transition-colors disabled:opacity-50"
              >
                {extracting ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    Extracting details...
                  </>
                ) : (
                  <>
                    <Sparkles className="w-3.5 h-3.5" />
                    Extract & Pre-fill Form
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Form */}
          <form onSubmit={handleGenerate} className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 space-y-5">
            <h3 className="text-sm font-bold text-slate-900 border-b border-slate-100 pb-3 flex items-center justify-between">
              <span>Document Form Fields</span>
              <span className="text-xs text-slate-400 font-normal">* Indicates required official field</span>
            </h3>

            {/* Suggested Ref No Confirmation Banner */}
            <div className="p-4 bg-slate-50 rounded-lg border border-slate-200 space-y-2">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                <div className="flex items-center gap-2">
                  <Hash className="w-4 h-4 text-slate-500" />
                  <span className="text-xs font-bold text-slate-800">Reference Number:</span>
                  <input
                    type="text"
                    value={formData.ref_no || ''}
                    readOnly={Boolean(refNoConfirmed && reservationId)}
                    onChange={(e) => {
                      setRefNoConfirmed(false);
                      setReservationId(null);
                      handleFieldChange('ref_no', e.target.value);
                    }}
                    placeholder="Click Reserve to allocate..."
                    className="font-mono text-xs px-2.5 py-1 bg-white border border-slate-300 rounded font-semibold text-slate-800"
                  />
                </div>
                <div>
                  {refNoConfirmed && reservationId ? (
                    <span className="inline-flex items-center gap-1.5 text-xs text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-md font-semibold border border-emerald-200">
                      <Check className="w-3.5 h-3.5" />
                      Ref No. Reserved
                    </span>
                  ) : (
                    <button
                      type="button"
                      onClick={handleConfirmRefNo}
                      disabled={reserving}
                      className="inline-flex items-center gap-1.5 text-xs text-amber-800 bg-amber-100 hover:bg-amber-200 px-3 py-1 rounded-md font-semibold border border-amber-300 transition-colors disabled:opacity-50"
                    >
                      {reserving ? (
                        <>
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          Reserving...
                        </>
                      ) : (
                        <>
                          <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                          Reserve Next Number
                        </>
                      )}
                    </button>
                  )}
                </div>
              </div>
              <p className="text-[11px] text-slate-500">
                Official institutional policy requires manual confirmation of all generated counter numbers.
              </p>
            </div>

            {/* Dynamic Fields */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {template?.fields.map((field) => {
                const prov = fieldProvenance[field.key];
                const isExtracted = prov && !prov.confirmed;
                const value = formData[field.key] !== undefined ? formData[field.key] : '';

                // Skip ref_no since it has dedicated confirmation banner above
                if (field.key === 'ref_no' || field.key === 'room_ref_no') return null;

                const isFullWidth = field.type === 'longtext' || field.key === 'event_name' || field.key === 'submitted_to';
                const labelText = formatAskLabel(field);

                return (
                  <div key={field.key} className={isFullWidth ? 'md:col-span-2' : ''}>
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <label className="text-xs font-semibold text-slate-700">
                          {labelText}
                          {field.required && <span className="text-red-500 ml-0.5">*</span>}
                        </label>
                        {field.default_source === 'club_settings' && (
                          <span className="bg-blue-50 text-[#1b365d] text-[10px] px-1.5 py-0.5 rounded border border-blue-200 font-semibold">
                            from club settings
                          </span>
                        )}
                      </div>
                      {isExtracted && (
                        <div className="inline-flex items-center gap-1.5">
                          <span className="text-[10px] bg-amber-50 text-amber-800 px-1.5 py-0.5 rounded border border-amber-200 font-semibold flex items-center gap-1">
                            <Sparkles className="w-3 h-3 text-amber-600" />
                            AI draft - review
                          </span>
                          <button
                            type="button"
                            onClick={() => confirmField(field.key)}
                            className="text-[10px] bg-emerald-100 hover:bg-emerald-200 text-emerald-800 px-2 py-0.5 rounded border border-emerald-300 font-bold"
                          >
                            Accept
                          </button>
                        </div>
                      )}
                    </div>

                    {field.type === 'longtext' ? (
                      <textarea
                        rows={3}
                        value={value}
                        onChange={(e) => handleFieldChange(field.key, e.target.value)}
                        placeholder={`Enter ${labelText}...`}
                        className={`w-full text-xs p-2.5 rounded-lg border ${
                          isExtracted
                            ? 'border-amber-400 bg-amber-50/20'
                            : 'border-slate-300 bg-white'
                        } focus:ring-2 focus:ring-[#1b365d] focus:border-transparent`}
                      />
                    ) : field.type === 'enum' || field.values ? (
                      <select
                        value={value}
                        onChange={(e) => handleFieldChange(field.key, e.target.value)}
                        className="w-full text-xs p-2.5 rounded-lg border border-slate-300 bg-white focus:ring-2 focus:ring-[#1b365d]"
                      >
                        {(field.values || ['Offline', 'Online', 'Hybrid']).map((v) => (
                          <option key={v} value={v}>
                            {v}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <input
                        type={field.type === 'date' ? 'date' : field.type === 'int' ? 'number' : 'text'}
                        value={value}
                        onChange={(e) => handleFieldChange(field.key, e.target.value)}
                        placeholder={`Enter ${labelText}...`}
                        className={`w-full text-xs p-2.5 rounded-lg border ${
                          isExtracted
                            ? 'border-amber-400 bg-amber-50/20'
                            : 'border-slate-300 bg-white'
                        } focus:ring-2 focus:ring-[#1b365d] focus:border-transparent`}
                      />
                    )}

                    {/* Defer OK Checkbox */}
                    {field.defer_ok && (
                      <label className="flex items-center gap-1.5 mt-1.5 text-[11px] text-slate-500 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={Boolean(deferredFields[field.key])}
                          onChange={(e) => {
                            const checked = e.target.checked;
                            setDeferredFields((prev) => ({ ...prev, [field.key]: checked }));
                          }}
                          className="rounded border-slate-300 text-[#1b365d] focus:ring-[#1b365d]"
                        />
                        <span>Leave blank for hand-filling</span>
                      </label>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Bottom Actions */}
            <div className="pt-4 border-t border-slate-100 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <button
                type="button"
                onClick={onCancel}
                className="px-4 py-2 text-xs font-semibold text-slate-600 hover:text-slate-800"
              >
                Cancel
              </button>

              <div className="flex items-center gap-3">
                {!canGenerate && (
                  <span className="text-xs text-amber-700 font-medium bg-amber-50 px-3 py-1 rounded-lg border border-amber-200">
                    {getGenerateButtonHint()}
                  </span>
                )}
                <button
                  type="submit"
                  disabled={!canGenerate || generating}
                  className="inline-flex items-center gap-2 bg-[#1b365d] hover:bg-[#152a48] text-white px-6 py-2.5 rounded-lg text-sm font-bold shadow-md transition-all disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {generating ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Rendering via LibreOffice...
                    </>
                  ) : (
                    <>
                      <FileText className="w-4 h-4" />
                      Generate Document
                    </>
                  )}
                </button>
              </div>
            </div>
          </form>
        </div>

        {/* Side Column: Missing-Info & Requirements Panel */}
        <div className="space-y-5">
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
            <div className="flex items-center justify-between mb-3 pb-2 border-b border-slate-100">
              <h3 className="font-bold text-slate-900 text-sm flex items-center gap-1.5">
                <Info className="w-4 h-4 text-blue-600" />
                Required Field Status
              </h3>
              <span
                className={`text-xs px-2 py-0.5 rounded-full font-bold ${
                  missingFields.length === 0 && refNoConfirmed
                    ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                    : 'bg-amber-100 text-amber-800 border border-amber-300'
                }`}
              >
                {missingFields.length === 0 && refNoConfirmed
                  ? 'All Complete ✓'
                  : `${missingFields.length + (!refNoConfirmed ? 1 : 0)} Pending`}
              </span>
            </div>

            <ul className="space-y-2 text-xs">
              {/* Reference Number Item (Amber until confirmed) */}
              <li
                className={`p-2 rounded-lg flex items-center justify-between border ${
                  refNoConfirmed
                    ? 'bg-emerald-50/50 border-emerald-100 text-emerald-900'
                    : 'bg-amber-50/60 border-amber-200 text-amber-900 font-medium'
                }`}
              >
                <div className="truncate pr-2">
                  <span>Reference Number ({formData.ref_no || 'Suggested'})</span>
                  {!refNoConfirmed && (
                    <span className="block text-[10px] text-amber-700 font-normal">
                      Suggested (Unconfirmed - Click to Confirm)
                    </span>
                  )}
                  {refNoConfirmed && (
                    <span className="block text-[10px] text-emerald-700 font-normal">
                      Confirmed ✓
                    </span>
                  )}
                </div>
                {refNoConfirmed ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                ) : (
                  <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0" />
                )}
              </li>

              {requiredFields.map((f) => {
                const isFilled = Boolean(formData[f.key] && String(formData[f.key]).trim());
                const isDeferred = Boolean(f.defer_ok && deferredFields[f.key]);
                const isReady = isFilled || isDeferred;
                const labelText = formatAskLabel(f);

                return (
                  <li
                    key={f.key}
                    className={`p-2 rounded-lg flex items-center justify-between border ${
                      isReady
                        ? 'bg-emerald-50/50 border-emerald-100 text-emerald-900'
                        : 'bg-amber-50/60 border-amber-200 text-amber-900 font-medium'
                    }`}
                  >
                    <div className="truncate pr-2">
                      <span>{labelText}</span>
                      {isDeferred && (
                        <span className="block text-[10px] text-slate-500 font-normal italic">
                          (Hand-fill deferred)
                        </span>
                      )}
                    </div>
                    {isReady ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                    ) : (
                      <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0" />
                    )}
                  </li>
                );
              })}
            </ul>
          </div>

          <div className="bg-blue-50/60 rounded-xl border border-blue-200/80 p-5 text-xs text-slate-700 space-y-2">
            <h4 className="font-bold text-[#1b365d] flex items-center gap-1.5">
              <Building className="w-4 h-4 text-[#1b365d]" />
              Institutional Standard
            </h4>
            <p>
              Generated documents adhere strictly to Dean (Students Welfare) and SVNIT academic guidelines:
            </p>
            <ul className="list-disc list-inside space-y-1 text-slate-600">
              <li>Full official SVNIT bilingual letterhead</li>
              <li>Dual-logo letterhead for student chapters</li>
              <li>Preserved 2x2 bordered approval signature blocks</li>
              <li>Official LibreOffice conversion with exact line wrapping</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};
