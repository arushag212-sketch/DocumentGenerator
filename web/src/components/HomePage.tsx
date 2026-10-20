import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { FileText, CheckSquare, Square, AlertCircle, ArrowRight, Calendar, Clock, MapPin, Users, HelpCircle, CheckCircle2, Award, Receipt, Megaphone, ClipboardList, LayoutTemplate } from 'lucide-react';
import { api } from '../api/client';
import { BatchRowsPanel, BatchRows } from './BatchRowsPanel';
import { HomeUnderstoodData, HomeRecommendedDoc, HomeMissingQuestion, HomeGenerateResponse } from '../types';

export const formatDateToIndian = (d: string): string => {
  if (!d || !d.includes('-')) return d;
  const parts = d.split('-');
  if (parts.length === 3) {
    const [y, m, day] = parts;
    return `${day}/${m}/${y}`;
  }
  return d;
};

export const formatTime12Hour = (time24: string): string => {
  if (!time24 || !time24.includes(':')) return time24;
  const [hStr, mStr] = time24.split(':');
  let h = parseInt(hStr, 10);
  if (isNaN(h)) return time24;
  const ampm = h >= 12 ? 'PM' : 'AM';
  h = h % 12 || 12;
  return `${h.toString().padStart(2, '0')}:${mStr} ${ampm}`;
};

export const formatIndianCurrency = (num: number | string): string => {
  const clean = typeof num === 'string' ? num.replace(/,/g, '') : num;
  const val = typeof clean === 'string' ? parseFloat(clean) : clean;
  if (isNaN(val)) return '₹0.00';
  return '₹' + val.toLocaleString('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
};

interface HomePageProps {
  clubId: string | number;
  initialTemplateId?: string | null;
  /** Sentence to prefill and analyse right away (e.g. the prompt an AI template came from). */
  initialPrompt?: string | null;
  initialText?: string;
  onDocumentsGenerated: (result: HomeGenerateResponse) => void;
}

/** Example requests a member can start from; they only fill the box, nothing runs until "Continue". */
const EXAMPLE_REQUESTS = [
  'We are conducting a two-day Web Development Workshop on 14–15 October in Seminar Hall for around 120 students.',
  'Certificates of participation for everyone who attended the Garba Night on 20 October.',
  'Minutes of the core committee meeting held today to plan the hackathon.',
  'Prize money receipts for the three winners of the coding contest.',
];

type TemplateOption = { key: string; name: string; description?: string; category?: string; is_system: boolean };

function templateIcon(t: TemplateOption): React.ElementType {
  const n = `${t.name} ${t.category || ''}`.toLowerCase();
  if (n.includes('certificate')) return Award;
  if (n.includes('minutes') || n.includes('meeting')) return Users;
  if (n.includes('bill') || n.includes('receipt') || n.includes('budget') || n.includes('sponsor')) return Receipt;
  if (n.includes('notice') || n.includes('circular')) return Megaphone;
  if (n.includes('report') || n.includes('proposal')) return ClipboardList;
  return FileText;
}

export const HomePage: React.FC<HomePageProps> = ({
  clubId,
  initialTemplateId = null,
  initialPrompt = null,
  initialText = '',
  onDocumentsGenerated,
}) => {
  const navigate = useNavigate();
  const [inputText, setInputText] = useState(initialText);
  const [understanding, setUnderstanding] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Response state from /home/understand
  const [understood, setUnderstood] = useState<HomeUnderstoodData | null>(null);
  const [recommendedDocs, setRecommendedDocs] = useState<HomeRecommendedDoc[]>([]);
  const [missingQuestions, setMissingQuestions] = useState<HomeMissingQuestion[]>([]);

  // User form / edits state
  const [selectedTemplateIds, setSelectedTemplateIds] = useState<string[]>([]);
  // Set when the page opens for one specific template (with its prompt): keep the
  // selection to that template instead of adding other recommendations.
  const exclusiveSelectionRef = useRef(false);
  const promptHandledRef = useRef<string | null>(null);
  const [refNumbersAccepted, setRefNumbersAccepted] = useState(false);
  const [answers, setAnswers] = useState<Record<string, any>>({});
  const [datesConfirmed, setDatesConfirmed] = useState(false);
  const [showOptionalDetails, setShowOptionalDetails] = useState(false);

  // Editable understood fields
  const [eventName, setEventName] = useState('');
  const [venue, setVenue] = useState('');
  const [dateStart, setDateStart] = useState('');
  const [dateEnd, setDateEnd] = useState('');
  const [timeStart, setTimeStart] = useState('');
  const [timeEnd, setTimeEnd] = useState('');
  const [participants, setParticipants] = useState<number | string>('');
  const [description, setDescription] = useState('');
  const [objectives, setObjectives] = useState('');
  const [detailSuggestions, setDetailSuggestions] = useState<string[]>([]);
  const [improvingText, setImprovingText] = useState(false);

  // Active events dropdown & People picker state
  const [activeEvents, setActiveEvents] = useState<any[]>([]);
  const [selectedEventId, setSelectedEventId] = useState<string>('');
  const [clubPeople, setClubPeople] = useState<any[]>([]);
  const [templateOptions, setTemplateOptions] = useState<TemplateOption[]>([]);
  const [batchRows, setBatchRows] = useState<BatchRows | null>(null);
  const textAreaRef = useRef<HTMLTextAreaElement>(null);

  const today = new Date();
  const minDate = new Date(today.getFullYear() - 1, today.getMonth(), today.getDate()).toISOString().split('T')[0];
  const maxDate = new Date(today.getFullYear() + 2, today.getMonth(), today.getDate()).toISOString().split('T')[0];

  useEffect(() => {
    if (clubId) {
      api.events.listActive(clubId)
        .then((data) => setActiveEvents((data || []).map((event) => ({ ...event, id: String(event.id) }))))
        .catch(() => {});
      api.clubs.getPeople(clubId)
        .then((data) => setClubPeople(data || []))
        .catch(() => {});
      // The club's published templates (built-in and its own), not a fixed list
      api.documents.listTemplates(clubId)
        .then((data) =>
          setTemplateOptions(
            (data || [])
              .filter((t: any) => t.status === 'published')
              .map((t: any) => ({ key: t.slug || t.id, name: t.name, description: t.description, category: t.category, is_system: !!t.is_system }))
              .sort((x: TemplateOption, y: TemplateOption) => Number(x.is_system) - Number(y.is_system) || x.name.localeCompare(y.name))
          )
        )
        .catch(() => setTemplateOptions([]));
    }
  }, [clubId]);

  const handleEventChange = (evId: string) => {
    setSelectedEventId(evId);
    if (!evId) {
      setInputText('');
      setUnderstood(null);
      setEventName('');
      setVenue('');
      setDateStart('');
      setDateEnd('');
      setTimeStart('');
      setTimeEnd('');
      setParticipants('');
      setDescription('');
      setObjectives('');
      setAnswers({});
      setSelectedTemplateIds([]);
      return;
    }
    const ev = activeEvents.find((e) => e.id === evId);
    if (ev) {
      const rec = ev.record || {};
      const title = ev.title || rec.event_name || '';
      setEventName(title);
      setVenue(rec.venue || '');
      setDateStart(rec.date_start || '');
      setDateEnd(rec.date_end || '');
      setTimeStart(rec.time_start || '');
      setTimeEnd(rec.time_end || '');
      setParticipants(rec.participants || rec.expected_participants || '');
      setDescription(rec.description || '');
      setObjectives(rec.objectives || '');
      const prompt = `${title} at ${rec.venue || 'campus'} on ${rec.dates || rec.date_start || 'upcoming'}`;
      setInputText(prompt);
      handleUnderstand(prompt, [selectedTemplateIds[0]].filter(Boolean));
    }
  };

  useEffect(() => {
    if (initialTemplateId) {
      setSelectedTemplateIds([initialTemplateId]);
      if (initialPrompt && initialPrompt.trim()) {
        // Coming from a specific template: generate just that document.
        if (promptHandledRef.current === `${initialTemplateId}:${initialPrompt}`) return;
        promptHandledRef.current = `${initialTemplateId}:${initialPrompt}`;
        exclusiveSelectionRef.current = true;
        setInputText(initialPrompt);
        handleUnderstand(initialPrompt, [initialTemplateId]);
        return;
      }
      exclusiveSelectionRef.current = true;
      textAreaRef.current?.focus();
    }
  }, [initialTemplateId]);

  const handleSelectDocType = (t: TemplateOption) => {
    const already = selectedTemplateIds.length === 1 && selectedTemplateIds[0] === t.key;
    setSelectedTemplateIds(already ? [] : [t.key]);
    exclusiveSelectionRef.current = !already;
    textAreaRef.current?.focus();
  };

  const handleUnderstand = async (textToUnderstand: string, selectedTemplateIdsOverride?: string[]) => {
    if (!textToUnderstand.trim() || textToUnderstand.trim().length < 2) return;
    setUnderstanding(true);
    setError(null);
    try {
      const res = await api.home.understand(clubId, {
        text: textToUnderstand,
        selected_template_ids: selectedTemplateIdsOverride || selectedTemplateIds,
      });

      setUnderstood(res.understood);
      setRecommendedDocs(res.recommended_documents);
      setMissingQuestions(res.missing_questions);

      // Pre-select recommended documents
      const recIds = res.recommended_documents
        .filter((d) => d.recommended)
        .map((d) => d.slug || d.template_id);
      const explicitIds = selectedTemplateIdsOverride || selectedTemplateIds;
      if (exclusiveSelectionRef.current && explicitIds.length > 0) {
        setSelectedTemplateIds(explicitIds);
      } else {
        setSelectedTemplateIds(Array.from(new Set([
          ...explicitIds,
          ...(recIds.length > 0 ? recIds : res.recommended_documents.slice(0, 1).map(d => d.slug || d.template_id)),
        ])));
      }

      setUnderstood(res.understood);
      setEventName(res.understood.event_name || '');
      setVenue(res.understood.venue || '');
      setDateStart(res.understood.date_start || '');
      setDateEnd(res.understood.date_end || '');
      setTimeStart(res.understood.time_start || '');
      setTimeEnd(res.understood.time_end || '');
      setParticipants(res.understood.participants || '');
      setDescription(res.understood.description || '');
      setObjectives(res.understood.objectives || '');

      // Core keys are already editable inputs in Section 1 (What we understood)
      const CORE_KEYS = new Set([
        'event_name', 'title', 'dates', 'date_start', 'date_end',
        'time_start', 'time_end', 'venue', 'participants', 'expected_participants',
        'description', 'objectives', 'dates_confirmation'
      ]);

      const additionalQuestions = (res.missing_questions || []).filter(
        (q: any) => !CORE_KEYS.has(q.key)
      );
      setMissingQuestions(additionalQuestions);

      // Initialize missing questions answers
      const initAnswers: Record<string, any> = {};
      additionalQuestions.forEach((q: any) => {
        if (q.current_value !== undefined && q.current_value !== null) {
          initAnswers[q.key] = q.current_value;
        } else if (q.values && q.values.length > 0) {
          initAnswers[q.key] = q.values[0];
        }
      });
      setAnswers(initAnswers);
      setRefNumbersAccepted(false);
    } catch (err: any) {
      setError(err.message || 'Could not understand requirements. Please try typing in different words.');
    } finally {
      setUnderstanding(false);
    }
  };

  const handleImproveText = async (
    text: string,
    mode: 'formal' | 'proofread' | 'longer' | 'shorter',
    setter: (val: string) => void
  ) => {
    if (!text || text.includes('[AI-drafted')) return;
    setImprovingText(true);
    try {
      const res = await api.documents.improveText(clubId, { text, mode });
      if (res && res.improved) {
        setter(res.improved);
      }
    } catch {
      // ignore
    } finally {
      setImprovingText(false);
    }
  };

  const handleSuggestDetails = async () => {
    try {
      const res = await api.documents.suggestDetails(clubId, {
        event_type: eventName || 'college_event',
        existing_fields: ['event_name', 'venue', 'date_start'],
      });
      if (res && Array.isArray(res.suggestions)) {
        setDetailSuggestions(
          res.suggestions.map((s: any) => (typeof s === 'string' ? s : s.label || s.ask || s.key))
        );
      }
    } catch {
      // ignore
    }
  };

  const handleChipClick = (example: string) => {
    setInputText(example);
    textAreaRef.current?.focus();
  };

  const handleToggleDoc = (templateSlug: string) => {
    setSelectedTemplateIds((prev) =>
      prev.includes(templateSlug) ? prev.filter((id) => id !== templateSlug) : [...prev, templateSlug]
    );
  };

  const hasUnconfirmedDraft =
    (description && description.includes('[AI-drafted')) ||
    (objectives && objectives.includes('[AI-drafted'));

  const handleGenerate = async (previewWithBlanks: boolean = false) => {
    if (selectedTemplateIds.length === 0) {
      setError('Please select at least one document to generate.');
      return;
    }
    if (!previewWithBlanks && !refNumbersAccepted) {
      setError('Please accept the suggested reference numbers before generating.');
      return;
    }
    if (!previewWithBlanks && description && description.includes('[AI-drafted')) {
      setError("Field 'Description' contains unconfirmed AI draft. Please accept or edit before generating.");
      return;
    }
    if (!previewWithBlanks && objectives && objectives.includes('[AI-drafted')) {
      setError("Field 'Objectives' contains unconfirmed AI draft. Please accept or edit before generating.");
      return;
    }

    if (!previewWithBlanks) {
      // Date range bounds checking (1 year in past to 2 years in future)
      if (dateStart && (dateStart < minDate || dateStart > maxDate)) {
        setError(`Start date must be between ${formatDateToIndian(minDate)} and ${formatDateToIndian(maxDate)}.`);
        return;
      }
      if (dateEnd && (dateEnd < minDate || dateEnd > maxDate)) {
        setError(`End date must be between ${formatDateToIndian(minDate)} and ${formatDateToIndian(maxDate)}.`);
        return;
      }

      // Time ordering check: if same day, end time must be strictly after start time
      if (timeStart && timeEnd) {
        if ((!dateStart && !dateEnd) || dateStart === dateEnd) {
          if (timeEnd <= timeStart) {
            setError('End time must be after start time.');
            return;
          }
        }
      }
    }

    setGenerating(true);
    setError(null);

    // Assemble unified event data
    const numParticipants = participants ? Number(participants) : undefined;
    const eventData: Record<string, any> = {
      ...understood?.raw,
      ...answers,
      event_name: eventName,
      venue: venue,
      participants: numParticipants,
      expected_participants: numParticipants,
      description: description,
      objectives: objectives,
    };

    if (batchRows && selectedTemplateIds.includes(batchRows.templateKey)) {
      eventData.rows = batchRows.rows;
      eventData.rows_for = batchRows.templateKey;
    }

    if (timeStart) eventData.time_start = timeStart;
    if (timeEnd) eventData.time_end = timeEnd;

    if (dateStart && dateEnd) {
      eventData.date_start = dateStart;
      eventData.date_end = dateEnd;
      eventData.dates_confirmed = true;
    } else if (understood?.dates) {
      eventData.dates = understood.dates;
      eventData.dates_confirmed = datesConfirmed || previewWithBlanks;
    }

    try {
      const response = await api.home.generate(clubId, {
        selected_template_ids: selectedTemplateIds,
        event_data: eventData,
        ref_numbers_accepted: true,
        event_id: selectedEventId || undefined,
        event_title: eventName || 'College Event',
        allow_blanks: previewWithBlanks,
      });
      onDocumentsGenerated(response);
    } catch (err: any) {
      setError(err.message || 'Generation failed. Please verify that all required fields are filled.');
    } finally {
      setGenerating(false);
    }
  };

  // Values that come from the spreadsheet rows are not asked again
  const rowKeys = new Set(batchRows && selectedTemplateIds.includes(batchRows.templateKey) ? batchRows.mappedKeys : []);
  const essentialQuestions = missingQuestions
    .filter((q) => !rowKeys.has(q.key))
    .filter((q) => q.importance === 'essential' || q.required)
    .slice(0, 6);

  const optionalQuestions = missingQuestions.filter(
    (q) => !essentialQuestions.includes(q) && !rowKeys.has(q.key)
  );

  const renderQuestionInput = (q: HomeMissingQuestion) => {
    const val = answers[q.key] ?? '';
    return (
      <div key={q.key} className="space-y-1.5">
        <label className="block text-xs sm:text-sm font-semibold text-slate-800">
          {q.question} {q.required && <span className="text-red-500">*</span>}
          {q.importance === 'optional' && !q.required && (
            <span className="ml-1.5 text-xs font-normal text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded">
              Optional
            </span>
          )}
        </label>
        <p className="text-xs text-slate-400">Needed for: {q.needed_by.join(', ')}</p>

        {/* Widget rendering based on type */}
        {(q.type === 'enum' || (q.values && q.values.length > 0)) ? (
          <select
            value={val}
            onChange={(e) => setAnswers({ ...answers, [q.key]: e.target.value })}
            className="w-full text-xs sm:text-sm bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:bg-white focus:outline-none focus:ring-1 focus:ring-brand-700"
          >
            <option value="">-- Select {q.label} --</option>
            {q.values?.map((opt) => (
              <option key={opt} value={opt}>{opt}</option>
            ))}
          </select>
        ) : (q.type === 'person' || q.key.includes('signatory') || q.key.includes('person') || q.key === 'faculty_incharge') && clubPeople.length > 0 ? (
          <select
            value={val}
            onChange={(e) => setAnswers({ ...answers, [q.key]: e.target.value })}
            className="w-full text-xs sm:text-sm bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:bg-white focus:outline-none focus:ring-1 focus:ring-brand-700"
          >
            <option value="">-- Select Person --</option>
            {clubPeople.map((p) => {
              const pName = p.full_name || p.name;
              const pDesig = p.roles?.[0]?.designation_label || p.designation || '';
              return (
                <option key={p.id} value={pName}>
                  {pName} {pDesig ? `(${pDesig})` : ''}
                </option>
              );
            })}
          </select>
        ) : q.type === 'time' ? (
          <div>
            <div className="flex justify-between items-center mb-1">
              {val && (
                <span className="text-xs font-bold text-brand-700 bg-brand-50 px-2 py-0.5 rounded border border-brand-200">
                  {formatTime12Hour(val)}
                </span>
              )}
            </div>
            <input
              type="time"
              value={val}
              onChange={(e) => setAnswers({ ...answers, [q.key]: e.target.value })}
              className="w-full text-xs sm:text-sm bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:bg-white focus:outline-none focus:ring-1 focus:ring-brand-700"
            />
          </div>
        ) : (q.type === 'money' || q.key === 'budget_items' || q.key.includes('amount') || q.key.includes('budget')) ? (
          <div>
            <div className="relative">
              <span className="absolute left-3 top-2.5 text-slate-500 font-bold text-xs">₹</span>
              <input
                type="number"
                step="0.01"
                min="0"
                value={val}
                onChange={(e) => setAnswers({ ...answers, [q.key]: e.target.value })}
                placeholder="e.g. 25000.00"
                className="w-full pl-8 pr-3 py-2 text-xs sm:text-sm bg-slate-50 border border-slate-200 rounded-xl text-slate-800 focus:bg-white focus:outline-none focus:ring-1 focus:ring-brand-700"
              />
            </div>
            {val && !isNaN(Number(val)) && (
              <p className="text-xs text-slate-500 mt-1 font-medium">
                Formatted: {formatIndianCurrency(val)}
              </p>
            )}
          </div>
        ) : (
          <div>
            <input
              type={q.type === 'int' ? 'number' : 'text'}
              step={q.type === 'int' ? '1' : undefined}
              min={q.type === 'int' ? '0' : undefined}
              value={val}
              onChange={(e) => setAnswers({ ...answers, [q.key]: e.target.value })}
              placeholder={
                q.key === 'judges'
                  ? 'e.g. Dr. Alok Kumar, Prof. Sharma (or leave blank if none)'
                  : q.label
              }
              className="w-full text-xs sm:text-sm bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:bg-white focus:outline-none focus:ring-1 focus:ring-brand-700"
            />
            {q.key === 'judges' && (
              <p className="text-xs text-slate-400 mt-1">
                Enter comma-separated names of external judges, or leave empty if none.
              </p>
            )}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6 px-4 sm:px-8 py-8">
      <div className="surface-card p-5 sm:p-6 space-y-5">
        <div className="flex flex-col md:flex-row md:items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <h1 className="page-title">Create documents</h1>
            <p className="page-subtitle">
              Describe the event or what you need in plain words. ClubDocs picks the documents, fills in what you said and asks for the rest.
            </p>
          </div>
          <label className="flex items-center gap-2 text-sm text-slate-600 self-start md:w-64 w-full flex-shrink-0">
            <span className="flex-shrink-0">Event</span>
            <select
              value={selectedEventId}
              onChange={(e) => handleEventChange(e.target.value)}
              className="input-field !py-1.5 min-w-0 truncate"
              title="Continue an existing event, or start a new one"
            >
              <option value="">New event</option>
              {activeEvents.map((ev) => (
                <option key={ev.id} value={ev.id}>
                  {ev.title} {ev.event_code ? `(${ev.event_code})` : ''}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div>
          <label htmlFor="request-text" className="field-label">What do you need?</label>
          <textarea
            id="request-text"
            ref={textAreaRef}
            rows={4}
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey) && inputText.trim()) handleUnderstand(inputText);
            }}
            placeholder="e.g. We are conducting a two-day Web Development Workshop on 14–15 October in Seminar Hall for around 120 students."
            className="input-field resize-y leading-relaxed"
          />
          <div className="mt-2 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex flex-wrap gap-x-3 gap-y-1 text-sm">
              <span className="text-slate-500">Try:</span>
              {EXAMPLE_REQUESTS.map((example) => (
                <button
                  key={example}
                  type="button"
                  onClick={() => handleChipClick(example)}
                  className="text-brand-700 hover:underline text-left"
                  title={example}
                >
                  {example.split(' ').slice(0, 4).join(' ')}…
                </button>
              ))}
            </div>
            <button
              type="button"
              onClick={() => handleUnderstand(inputText)}
              disabled={understanding || !inputText.trim()}
              className="btn-primary flex-shrink-0 self-end sm:self-auto"
            >
              {understanding ? (
                <>
                  <span className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Reading your request…
                </>
              ) : (
                <>
                  Continue
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between mb-2">
            <p className="field-label !mb-0">Or pick a document type <span className="font-normal text-slate-500">(optional)</span></p>
            <button type="button" onClick={() => navigate('/templates')} className="text-sm text-brand-700 hover:underline inline-flex items-center gap-1">
              <LayoutTemplate className="w-4 h-4" /> Manage templates
            </button>
          </div>
          {templateOptions.length === 0 ? (
            <p className="text-sm text-slate-500">No published templates yet.</p>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
              {templateOptions.map((t) => {
                const Icon = templateIcon(t);
                const isSelected = selectedTemplateIds.includes(t.key);
                return (
                  <button
                    key={t.key}
                    type="button"
                    aria-pressed={isSelected}
                    onClick={() => handleSelectDocType(t)}
                    className={`flex items-start gap-2.5 p-2.5 rounded-lg border text-left transition-colors ${
                      isSelected ? 'border-brand-700 bg-brand-50' : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50'
                    }`}
                  >
                    <Icon className={`w-4 h-4 mt-0.5 flex-shrink-0 ${isSelected ? 'text-brand-700' : 'text-slate-400'}`} />
                    <span className="min-w-0">
                      <span className="block text-sm font-medium text-slate-900 truncate">{t.name}</span>
                      <span className="block text-xs text-slate-500 truncate">
                        {t.is_system ? 'Built-in' : 'Club template'}
                        {t.description ? ` · ${t.description}` : ''}
                      </span>
                    </span>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-red-800 text-xs sm:text-sm flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div className="flex items-start gap-2.5">
            <AlertCircle className="w-5 h-5 flex-shrink-0 text-red-600 mt-0.5" />
            <div className="font-medium leading-relaxed">{error}</div>
          </div>
          {selectedTemplateIds.length > 0 && (
            <button
              type="button"
              onClick={() => handleGenerate(true)}
              className="flex-shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-slate-50 text-slate-800 font-semibold text-xs border border-slate-300 rounded-lg shadow-xs transition-colors cursor-pointer"
              title="Generate and preview document with clean blank lines for unfilled fields"
            >
              <FileText className="w-3.5 h-3.5 text-slate-600" />
              Preview with blanks instead
            </button>
          )}
        </div>
      )}

      {/* Main Flow: What was Understood + Recommendations + Questions */}
      {understood && (
        <div className="space-y-6">
          {/* 1. What was Understood */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5 sm:p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
                <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                What we understood
              </h2>
              <span className="text-xs font-medium text-slate-400">Click any field to edit</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs sm:text-sm">
              {/* Event Name */}
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1">Event Title</label>
                <input
                  type="text"
                  value={eventName}
                  onChange={(e) => setEventName(e.target.value)}
                  placeholder="e.g. Web Development Workshop"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:bg-white focus:outline-none focus:ring-1 focus:ring-brand-700"
                />
              </div>

              {/* Venue */}
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1 flex items-center gap-1">
                  <MapPin className="w-3.5 h-3.5 text-slate-400" />
                  Venue
                </label>
                <input
                  type="text"
                  value={venue}
                  onChange={(e) => setVenue(e.target.value)}
                  placeholder="e.g. Seminar Hall"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:bg-white focus:outline-none focus:ring-1 focus:ring-brand-700"
                />
              </div>

              {/* Date Start & Date End (Native Pickers) */}
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1 flex items-center justify-between">
                  <span className="flex items-center gap-1">
                    <Calendar className="w-3.5 h-3.5 text-slate-400" />
                    Start Date
                  </span>
                  {dateStart && (
                    <span className="text-xs font-bold text-brand-700 bg-brand-50 px-2 py-0.5 rounded border border-brand-200">
                      {formatDateToIndian(dateStart)}
                    </span>
                  )}
                </label>
                <input
                  type="date"
                  min={minDate}
                  max={maxDate}
                  value={dateStart}
                  onChange={(e) => setDateStart(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:bg-white focus:outline-none focus:ring-1 focus:ring-brand-700"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1 flex items-center justify-between">
                  <span className="flex items-center gap-1">
                    <Calendar className="w-3.5 h-3.5 text-slate-400" />
                    End Date
                  </span>
                  {dateEnd && (
                    <span className="text-xs font-bold text-brand-700 bg-brand-50 px-2 py-0.5 rounded border border-brand-200">
                      {formatDateToIndian(dateEnd)}
                    </span>
                  )}
                </label>
                <input
                  type="date"
                  min={minDate}
                  max={maxDate}
                  value={dateEnd}
                  onChange={(e) => setDateEnd(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:bg-white focus:outline-none focus:ring-1 focus:ring-brand-700"
                />
              </div>

              {/* Inferred dates confirmation checkbox if no picker dates set */}
              {understood.dates && (!dateStart || !dateEnd) && (
                <div className="sm:col-span-2 p-3 bg-amber-50/70 border border-amber-200 rounded-xl flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="confirmDatesYear"
                    checked={datesConfirmed}
                    onChange={(e) => setDatesConfirmed(e.target.checked)}
                    className="h-4 w-4 rounded border-slate-300 text-brand-700 focus:ring-brand-700"
                  />
                  <label htmlFor="confirmDatesYear" className="text-xs text-amber-950 font-medium cursor-pointer">
                    Confirm schedule dates: <strong>{understood.dates}</strong>
                  </label>
                </div>
              )}

              {/* Time Start & Time End (Native 24-hr Pickers) */}
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1 flex items-center justify-between">
                  <span className="flex items-center gap-1">
                    <Clock className="w-3.5 h-3.5 text-slate-400" />
                    Start Time
                  </span>
                  {timeStart && (
                    <span className="text-xs font-bold text-brand-700 bg-brand-50 px-2 py-0.5 rounded border border-brand-200">
                      {formatTime12Hour(timeStart)}
                    </span>
                  )}
                </label>
                <input
                  type="time"
                  value={timeStart}
                  onChange={(e) => setTimeStart(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:bg-white focus:outline-none focus:ring-1 focus:ring-brand-700"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1 flex items-center justify-between">
                  <span className="flex items-center gap-1">
                    <Clock className="w-3.5 h-3.5 text-slate-400" />
                    End Time
                  </span>
                  {timeEnd && (
                    <span className="text-xs font-bold text-brand-700 bg-brand-50 px-2 py-0.5 rounded border border-brand-200">
                      {formatTime12Hour(timeEnd)}
                    </span>
                  )}
                </label>
                <input
                  type="time"
                  value={timeEnd}
                  onChange={(e) => setTimeEnd(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:bg-white focus:outline-none focus:ring-1 focus:ring-brand-700"
                />
              </div>

              {/* Participants */}
              <div className="sm:col-span-2">
                <label className="block text-xs font-semibold text-slate-600 mb-1 flex items-center gap-1">
                  <Users className="w-3.5 h-3.5 text-slate-400" />
                  Expected Participants
                </label>
                <input
                  type="number"
                  min="0"
                  step="1"
                  value={participants}
                  onChange={(e) => setParticipants(e.target.value)}
                  placeholder="e.g. 120"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:bg-white focus:outline-none focus:ring-1 focus:ring-brand-700"
                />
              </div>

              {/* Description & Objectives (with Write a draft for me and AI draft accept buttons) */}
              {[
                { label: 'Description', val: description, setVal: setDescription, btnId: 'acceptAiDraftDescription' },
                { label: 'Objectives', val: objectives, setVal: setObjectives, btnId: 'acceptAiDraftObjectives' },
              ].map(({ label, val, setVal, btnId }) => (
                <div key={label} className="sm:col-span-2">
                  <div className="flex items-center justify-between mb-1">
                    <label className="block text-xs font-semibold text-slate-600">{label} (Optional)</label>
                    <div className="flex items-center gap-2">
                      {!val && (
                        <button
                          type="button"
                          disabled={improvingText || !eventName.trim()}
                          title={eventName.trim() ? undefined : 'Add the event name first'}
                          onClick={() => {
                            // Drafted by the AI from the facts on this form only; marked for review.
                            const facts = [
                              `${label} of ${eventName}`,
                              venue && `at ${venue}`,
                              dateStart && `on ${formatDateToIndian(dateStart)}`,
                              participants && `for ${participants} participants`,
                            ].filter(Boolean).join(' ');
                            handleImproveText(facts + '.', 'longer', (text) => setVal(`[AI-drafted] ${text}`));
                          }}
                          className="btn-ghost !px-2 !py-0.5 text-xs"
                        >
                          {improvingText ? 'Drafting…' : 'Draft with AI'}
                        </button>
                      )}
                      {val && val.includes('[AI-drafted') && (
                        <button
                          type="button"
                          id={btnId}
                          onClick={() => setVal(val.replace(/\[AI-drafted[^\]]*\]\s*/g, '').trim())}
                          className="text-xs font-semibold text-amber-800 bg-amber-100 hover:bg-amber-200 px-2 py-0.5 rounded transition-colors cursor-pointer"
                        >
                          Accept AI Draft
                        </button>
                      )}
                      {val && !val.includes('[AI-drafted') && (
                        <div className="flex items-center gap-1">
                          <button
                            type="button"
                            disabled={improvingText}
                            onClick={() => handleImproveText(val, 'formal', setVal)}
                            className="text-xs font-medium text-slate-600 hover:text-brand-600 bg-slate-100 hover:bg-brand-50 px-2 py-0.5 rounded transition cursor-pointer"
                          >
                            Make Formal
                          </button>
                          <button
                            type="button"
                            disabled={improvingText}
                            onClick={() => handleImproveText(val, 'proofread', setVal)}
                            className="text-xs font-medium text-slate-600 hover:text-brand-600 bg-slate-100 hover:bg-brand-50 px-2 py-0.5 rounded transition cursor-pointer"
                          >
                            Proofread
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                  <textarea
                    rows={2}
                    value={val}
                    onChange={(e) => setVal(e.target.value)}
                    placeholder={`Leave blank to omit or write a custom ${label.toLowerCase()}...`}
                    className="w-full text-xs sm:text-sm bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:bg-white focus:outline-none focus:ring-1 focus:ring-brand-700"
                  />
                  {label === 'Description' && (
                    <div className="mt-1 flex items-center gap-1.5 flex-wrap">
                      <button
                        type="button"
                        onClick={handleSuggestDetails}
                        className="text-xs font-semibold text-brand-700 bg-brand-50/70 hover:bg-brand-100 px-2 py-0.5 rounded border border-brand-200 transition-colors flex items-center gap-1 cursor-pointer"
                      >
                        Suggest optional details
                      </button>
                      {detailSuggestions.map((sug, sIdx) => (
                        <button
                          key={sIdx}
                          type="button"
                          onClick={() => {
                            setVal(val ? `${val}\n• ${sug}` : `• ${sug}`);
                            setDetailSuggestions((prev) => prev.filter((_, idx) => idx !== sIdx));
                          }}
                          className="text-xs text-slate-600 bg-slate-100 hover:bg-slate-200 px-2 py-0.5 rounded transition cursor-pointer"
                        >
                          + {sug}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* 2. Recommended Documents */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5 sm:p-6 space-y-4">
            <div className="border-b border-slate-100 pb-3">
              <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
                <FileText className="w-5 h-5 text-brand-700" />
                Recommended documents
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Select the documents you wish to generate in this batch.
              </p>
            </div>

            <div className="space-y-3">
              {recommendedDocs.map((doc) => {
                const isSelected = selectedTemplateIds.includes(doc.slug || doc.template_id);
                return (
                  <div
                    key={doc.template_id}
                    onClick={() => handleToggleDoc(doc.slug || doc.template_id)}
                    className={`p-4 rounded-xl border transition-all cursor-pointer flex items-start gap-3.5 ${
                      isSelected
                        ? 'border-brand-700 bg-brand-50/40'
                        : 'border-slate-200 hover:border-slate-300 bg-white'
                    }`}
                  >
                    <div className="mt-0.5 text-brand-700">
                      {isSelected ? (
                        <CheckSquare className="w-5 h-5 text-brand-700" />
                      ) : (
                        <Square className="w-5 h-5 text-slate-400" />
                      )}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-bold text-sm text-slate-900">{doc.name}</span>
                        {doc.recommended && (
                          <span className="px-2 py-0.5 text-xs font-semibold bg-emerald-100 text-emerald-800 rounded">
                            Recommended
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-slate-600 mt-1 leading-relaxed">{doc.reason}</p>
                      <div className="mt-2 text-xs font-mono text-slate-600 bg-slate-100/90 px-2.5 py-1 rounded-lg inline-block border border-slate-200">
                        {doc.suggested_ref_no}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Reference Numbers Acceptance */}
            <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-2 mt-4">
              <div className="flex items-start gap-2.5">
                <input
                  type="checkbox"
                  id="acceptRefNumbers"
                  checked={refNumbersAccepted}
                  onChange={(e) => setRefNumbersAccepted(e.target.checked)}
                  className="mt-0.5 h-4 w-4 rounded border-slate-300 text-brand-700 focus:ring-brand-700"
                />
                <label htmlFor="acceptRefNumbers" className="text-xs sm:text-sm font-semibold text-slate-800 cursor-pointer">
                  I accept the suggested reference numbers for the selected documents.
                </label>
              </div>
              <p className="text-xs text-slate-500 pl-6 leading-relaxed">
                Official reference numbers are safely allocated in unbroken sequence only when you generate.
              </p>
            </div>
          </div>

          {/* Spreadsheet batch: one document per row */}
          <BatchRowsPanel
            clubId={clubId}
            templates={recommendedDocs
              .filter((d) => selectedTemplateIds.includes(d.slug || d.template_id))
              .map((d) => ({ key: d.slug || d.template_id, name: d.name }))}
            value={batchRows}
            onChange={setBatchRows}
          />

          {/* 3. Grouped Essential Missing Questions */}
          {essentialQuestions.length > 0 && (
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5 sm:p-6 space-y-4">
              <div className="border-b border-slate-100 pb-3">
                <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
                  <HelpCircle className="w-5 h-5 text-amber-600" />
                  Additional details needed
                </h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  Essential details required to generate your official document.
                </p>
              </div>

              <div className="space-y-4">
                {essentialQuestions.map(renderQuestionInput)}
              </div>
            </div>
          )}

          {/* 4. Collapsible Optional Details (Bank, PAN, GST, etc.) */}
          {optionalQuestions.length > 0 && (
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
              <button
                type="button"
                id="toggleOptionalDetailsBtn"
                onClick={() => setShowOptionalDetails(!showOptionalDetails)}
                className="w-full p-4 sm:p-5 bg-slate-50/70 hover:bg-slate-100/70 flex items-center justify-between text-left transition-colors cursor-pointer"
              >
                <div>
                  <div className="text-sm font-bold text-slate-800 flex items-center gap-2">
                    <span>Add more details (optional)</span>
                    <span className="text-xs font-normal text-slate-500 bg-slate-200/60 px-2 py-0.5 rounded-full">
                      {optionalQuestions.length} optional field{optionalQuestions.length === 1 ? '' : 's'}
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Bank details, account numbers, IFSC, PAN, GST, etc. Unfilled fields render as clean blank lines ready to fill by hand.
                  </p>
                </div>
                <span className="text-xs font-semibold text-brand-700">
                  {showOptionalDetails ? '▲ Hide' : '▼ Show'}
                </span>
              </button>
              {showOptionalDetails && (
                <div className="p-5 sm:p-6 space-y-4 border-t border-slate-100 bg-white">
                  {optionalQuestions.map(renderQuestionInput)}
                </div>
              )}
            </div>
          )}

          {/* Bottom Generate Action Button */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-2">
            <div className="space-y-1">
              <div className="text-xs text-slate-500">
                {selectedTemplateIds.length} document{selectedTemplateIds.length === 1 ? '' : 's'} selected for generation
              </div>
              {hasUnconfirmedDraft && (
                <div className="text-xs text-amber-700 bg-amber-50 border border-amber-200 px-2.5 py-1 rounded-lg flex items-center gap-1.5 font-medium">
                  <AlertCircle className="w-3.5 h-3.5 text-amber-600 flex-shrink-0" />
                  Please accept or edit AI-drafted text (Description / Objectives) before generating.
                </div>
              )}
            </div>
            <div className="flex items-center gap-3 w-full sm:w-auto">
              <button
                type="button"
                id="previewWithBlanksBtn"
                onClick={() => handleGenerate(true)}
                disabled={generating || selectedTemplateIds.length === 0}
                className="w-full sm:w-auto px-5 py-3 bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 font-bold text-sm rounded-xl shadow-xs flex items-center justify-center gap-2 transition-all cursor-pointer disabled:opacity-50"
                title="Generate with clean blank lines for hand-filling"
              >
                <FileText className="w-4 h-4 text-slate-600" />
                Preview with blanks
              </button>
              <button
                type="button"
                id="generateDocumentsBtn"
                onClick={() => handleGenerate(false)}
                disabled={generating || selectedTemplateIds.length === 0 || !refNumbersAccepted || Boolean(hasUnconfirmedDraft)}
                className="w-full sm:w-auto px-6 py-3 bg-brand-700 hover:bg-brand-800 text-white font-bold text-sm rounded-xl shadow-md flex items-center justify-center gap-2 disabled:opacity-50 transition-all cursor-pointer disabled:cursor-not-allowed"
              >
                {generating ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    Generating Documents...
                  </>
                ) : (
                  <>
                    Generate Documents
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
