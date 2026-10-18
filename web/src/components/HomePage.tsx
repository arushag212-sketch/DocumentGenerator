import React, { useState, useEffect } from 'react';
import { Sparkles, FileText, CheckSquare, Square, AlertCircle, ArrowRight, Calendar, Clock, MapPin, Users, HelpCircle, CheckCircle2 } from 'lucide-react';
import { api } from '../api/client';
import { HomeUnderstoodData, HomeRecommendedDoc, HomeMissingQuestion, HomeGenerateResponse } from '../types';

interface HomePageProps {
  clubId: string | number;
  initialTemplateId?: string | null;
  initialText?: string;
  onDocumentsGenerated: (result: HomeGenerateResponse) => void;
}

export const STANDARD_DOC_TYPES = [
  {
    slug: 'permission_letter',
    name: 'Permission Letter',
    desc: 'Venue & classroom permission',
    icon: '🏛️',
    defaultPrompt: 'Permission letter to organize a technical workshop in Seminar Hall on 15 October 2026 from 9:00 AM to 5:00 PM for 120 students.',
  },
  {
    slug: 'approval_note',
    name: 'Approval Note',
    desc: 'Event proposal & budget sanction',
    icon: '📑',
    defaultPrompt: 'Approval note for Annual Coding Conclave with budget sanction of Rs 25000 on 10 November 2026.',
  },
  {
    slug: 'bill_certificate',
    name: 'Bill Certificate',
    desc: 'Expenditure verification',
    icon: '🧾',
    defaultPrompt: 'Bill certificate verifying expenditure for banners, stage decoration, and guest hospitality.',
  },
  {
    slug: 'bill_summary',
    name: 'Bill Summary',
    desc: 'Consolidated expense table',
    icon: '📊',
    defaultPrompt: 'Bill summary table for hackathon expenses including refreshment, prizes, and certificates.',
  },
  {
    slug: 'prize_money_receipts',
    name: 'Prize Receipts',
    desc: 'Student prize distribution',
    icon: '🏆',
    defaultPrompt: 'Prize money receipts for 1st, 2nd, and 3rd place winners of Annual Coding Hackathon.',
  },
  {
    slug: 'minutes_of_meeting',
    name: 'Minutes of Meeting',
    desc: 'Club meeting resolutions',
    icon: '⏱️',
    defaultPrompt: 'Minutes of meeting held on 10 October to plan upcoming semester technical events and core team tasks.',
  },
];

const EXAMPLE_CHIPS = [
  'Permission letter for an event',
  'Prize money receipts',
  'Bill summary',
  'Minutes of meeting',
  'Approval note',
  'Bill certificate',
];

export const HomePage: React.FC<HomePageProps> = ({
  clubId,
  initialTemplateId = null,
  initialText = '',
  onDocumentsGenerated,
}) => {
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
  const [refNumbersAccepted, setRefNumbersAccepted] = useState(false);
  const [answers, setAnswers] = useState<Record<string, any>>({});
  const [datesConfirmed, setDatesConfirmed] = useState(false);

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

  useEffect(() => {
    if (initialTemplateId) {
      setSelectedTemplateIds([initialTemplateId]);
      const matched = STANDARD_DOC_TYPES.find((d) => d.slug === initialTemplateId);
      if (matched && !inputText) {
        setInputText(matched.defaultPrompt);
        handleUnderstand(matched.defaultPrompt);
      }
    }
  }, [initialTemplateId]);

  const handleSelectDocType = (docType: typeof STANDARD_DOC_TYPES[0]) => {
    setSelectedTemplateIds([docType.slug]);
    setInputText(docType.defaultPrompt);
    handleUnderstand(docType.defaultPrompt);
  };

  const handleUnderstand = async (textToUnderstand: string) => {
    if (!textToUnderstand.trim() || textToUnderstand.trim().length < 2) return;
    setUnderstanding(true);
    setError(null);
    try {
      const res = await api.home.understand(clubId, {
        text: textToUnderstand,
      });

      setUnderstood(res.understood);
      setRecommendedDocs(res.recommended_documents);
      setMissingQuestions(res.missing_questions);

      // Pre-select recommended documents
      const recIds = res.recommended_documents
        .filter((d) => d.recommended)
        .map((d) => d.slug || d.template_id);
      setSelectedTemplateIds(recIds.length > 0 ? recIds : res.recommended_documents.slice(0, 1).map(d => d.slug || d.template_id));

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

  const handleChipClick = (chipText: string) => {
    const fullPrompt = `${chipText} for our upcoming college event`;
    setInputText(fullPrompt);
    handleUnderstand(fullPrompt);
  };

  const handleToggleDoc = (templateSlug: string) => {
    setSelectedTemplateIds((prev) =>
      prev.includes(templateSlug) ? prev.filter((id) => id !== templateSlug) : [...prev, templateSlug]
    );
  };

  const hasUnconfirmedDraft =
    (description && description.includes('[AI-drafted')) ||
    (objectives && objectives.includes('[AI-drafted'));

  const handleGenerate = async () => {
    if (selectedTemplateIds.length === 0) {
      setError('Please select at least one document to generate.');
      return;
    }
    if (!refNumbersAccepted) {
      setError('Please accept the suggested reference numbers before generating.');
      return;
    }
    if (description && description.includes('[AI-drafted')) {
      setError("Field 'Description' contains unconfirmed AI draft. Please accept or edit before generating.");
      return;
    }
    if (objectives && objectives.includes('[AI-drafted')) {
      setError("Field 'Objectives' contains unconfirmed AI draft. Please accept or edit before generating.");
      return;
    }

    setGenerating(true);
    setError(null);

    // Assemble unified event data
    const eventData: Record<string, any> = {
      ...understood?.raw,
      ...answers,
      event_name: eventName,
      venue: venue,
      participants: participants ? Number(participants) : undefined,
      description: description,
      objectives: objectives,
    };

    if (timeStart) eventData.time_start = timeStart;
    if (timeEnd) eventData.time_end = timeEnd;

    if (dateStart && dateEnd) {
      eventData.date_start = dateStart;
      eventData.date_end = dateEnd;
      eventData.dates_confirmed = true;
    } else if (understood?.dates) {
      eventData.dates = understood.dates;
      eventData.dates_confirmed = datesConfirmed;
    }

    if (timeStart) eventData.time_start = timeStart;
    if (timeEnd) eventData.time_end = timeEnd;

    try {
      const response = await api.home.generate(clubId, {
        selected_template_ids: selectedTemplateIds,
        event_data: eventData,
        ref_numbers_accepted: true,
        event_title: eventName || 'College Event',
      });
      onDocumentsGenerated(response);
    } catch (err: any) {
      setError(err.message || 'Generation failed. Please verify that all required fields are filled.');
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6 pb-12">
      {/* Hero / Big Input Card */}
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-5 sm:p-7 space-y-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-extrabold text-slate-900 tracking-tight flex items-center gap-2">
            <Sparkles className="w-6 h-6 text-amber-500 flex-shrink-0" />
            What do you need?
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            Type in plain words what document or package you want to draft, or click an example below.
          </p>
        </div>

        {/* Document Type Picker */}
        <div className="space-y-2 pt-1">
          <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider">
            1. Select Document Type
          </label>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
            {STANDARD_DOC_TYPES.map((docType) => {
              const isSelected = selectedTemplateIds.includes(docType.slug);
              return (
                <button
                  key={docType.slug}
                  type="button"
                  onClick={() => handleSelectDocType(docType)}
                  className={`p-3 rounded-xl border text-left transition-all flex flex-col justify-between ${
                    isSelected
                      ? 'border-[#1b365d] bg-blue-50/70 ring-1 ring-[#1b365d] shadow-xs'
                      : 'border-slate-200 bg-slate-50/50 hover:bg-slate-100 hover:border-slate-300'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <span className="text-lg">{docType.icon}</span>
                    <span className="text-xs font-bold text-slate-900 leading-tight">
                      {docType.name}
                    </span>
                  </div>
                  <p className="text-[10px] text-slate-500 mt-1 line-clamp-1">
                    {docType.desc}
                  </p>
                </button>
              );
            })}
          </div>
        </div>

        <div>
          <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
            2. Describe Details in Plain English
          </label>
          {/* Example Chips */}
          <div className="flex flex-wrap gap-2 pb-2">
            {EXAMPLE_CHIPS.map((chip) => (
              <button
                key={chip}
                type="button"
                onClick={() => handleChipClick(chip)}
                className="text-xs font-medium px-3 py-1.5 rounded-full bg-slate-100 text-slate-700 hover:bg-[#1b365d] hover:text-white transition-colors border border-slate-200"
              >
                {chip}
              </button>
            ))}
          </div>
        </div>

        {/* Input Text Box */}
        <div className="relative">
          <textarea
            rows={3}
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder="e.g. We are conducting a two-day Web Development Workshop on 14-15 October in Seminar Hall for around 120 students."
            className="w-full text-xs sm:text-sm p-3.5 bg-slate-50 border border-slate-200 rounded-xl focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#1b365d]/20 focus:border-[#1b365d] transition-all resize-none text-slate-800 leading-relaxed"
          />
          <div className="flex justify-end mt-2">
            <button
              type="button"
              onClick={() => handleUnderstand(inputText)}
              disabled={understanding || !inputText.trim()}
              className="px-4 py-2 bg-[#1b365d] hover:bg-[#132742] text-white text-xs sm:text-sm font-semibold rounded-xl shadow-sm flex items-center gap-1.5 disabled:opacity-50 transition-colors"
            >
              {understanding ? (
                <>
                  <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Understanding...
                </>
              ) : (
                <>
                  Understand & Recommend
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-red-800 text-xs sm:text-sm flex items-start gap-2.5">
          <AlertCircle className="w-5 h-5 flex-shrink-0 text-red-600 mt-0.5" />
          <div className="flex-1 font-medium">{error}</div>
        </div>
      )}

      {/* Main Flow: What was Understood + Recommendations + Questions */}
      {understood && (
        <div className="space-y-6">
          {/* 1. What was Understood */}
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-5 sm:p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
                <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                What we understood
              </h2>
              <span className="text-[11px] font-medium text-slate-400">Click any field to edit</span>
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
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:bg-white focus:outline-none focus:ring-1 focus:ring-[#1b365d]"
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
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:bg-white focus:outline-none focus:ring-1 focus:ring-[#1b365d]"
                />
              </div>

              {/* Date Start & Date End (Native Pickers) */}
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1 flex items-center gap-1">
                  <Calendar className="w-3.5 h-3.5 text-slate-400" />
                  Start Date
                </label>
                <input
                  type="date"
                  value={dateStart}
                  onChange={(e) => setDateStart(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:bg-white focus:outline-none focus:ring-1 focus:ring-[#1b365d]"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1 flex items-center gap-1">
                  <Calendar className="w-3.5 h-3.5 text-slate-400" />
                  End Date
                </label>
                <input
                  type="date"
                  value={dateEnd}
                  onChange={(e) => setDateEnd(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:bg-white focus:outline-none focus:ring-1 focus:ring-[#1b365d]"
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
                    className="h-4 w-4 rounded border-slate-300 text-[#1b365d] focus:ring-[#1b365d]"
                  />
                  <label htmlFor="confirmDatesYear" className="text-xs text-amber-950 font-medium cursor-pointer">
                    Confirm schedule dates: <strong>{understood.dates}</strong>
                  </label>
                </div>
              )}

              {/* Time Start & Time End (Native 24-hr Pickers) */}
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1 flex items-center gap-1">
                  <Clock className="w-3.5 h-3.5 text-slate-400" />
                  Start Time
                </label>
                <input
                  type="time"
                  value={timeStart}
                  onChange={(e) => setTimeStart(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:bg-white focus:outline-none focus:ring-1 focus:ring-[#1b365d]"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1 flex items-center gap-1">
                  <Clock className="w-3.5 h-3.5 text-slate-400" />
                  End Time
                </label>
                <input
                  type="time"
                  value={timeEnd}
                  onChange={(e) => setTimeEnd(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:bg-white focus:outline-none focus:ring-1 focus:ring-[#1b365d]"
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
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:bg-white focus:outline-none focus:ring-1 focus:ring-[#1b365d]"
                />
              </div>

              {/* Description (with AI draft accept button if flagged) */}
              {description && (
                <div className="sm:col-span-2">
                  <div className="flex items-center justify-between mb-1">
                    <label className="block text-xs font-semibold text-slate-600">
                      Description
                    </label>
                    {description.includes('[AI-drafted') && (
                      <button
                        type="button"
                        id="acceptAiDraftDescription"
                        onClick={() => setDescription(description.replace(/\[AI-drafted[^\]]*\]\s*/g, '').trim())}
                        className="text-[11px] font-semibold text-amber-800 bg-amber-100 hover:bg-amber-200 px-2 py-0.5 rounded transition-colors cursor-pointer"
                      >
                        Accept AI Draft
                      </button>
                    )}
                  </div>
                  <textarea
                    rows={2}
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    className="w-full text-xs sm:text-sm bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:bg-white focus:outline-none focus:ring-1 focus:ring-[#1b365d]"
                  />
                </div>
              )}

              {/* Objectives (with AI draft accept button if flagged) */}
              {objectives && (
                <div className="sm:col-span-2">
                  <div className="flex items-center justify-between mb-1">
                    <label className="block text-xs font-semibold text-slate-600">
                      Objectives
                    </label>
                    {objectives.includes('[AI-drafted') && (
                      <button
                        type="button"
                        id="acceptAiDraftObjectives"
                        onClick={() => setObjectives(objectives.replace(/\[AI-drafted[^\]]*\]\s*/g, '').trim())}
                        className="text-[11px] font-semibold text-amber-800 bg-amber-100 hover:bg-amber-200 px-2 py-0.5 rounded transition-colors cursor-pointer"
                      >
                        Accept AI Draft
                      </button>
                    )}
                  </div>
                  <textarea
                    rows={2}
                    value={objectives}
                    onChange={(e) => setObjectives(e.target.value)}
                    className="w-full text-xs sm:text-sm bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:bg-white focus:outline-none focus:ring-1 focus:ring-[#1b365d]"
                  />
                </div>
              )}
            </div>
          </div>

          {/* 2. Recommended Documents */}
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-5 sm:p-6 space-y-4">
            <div className="border-b border-slate-100 pb-3">
              <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
                <FileText className="w-5 h-5 text-[#1b365d]" />
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
                        ? 'border-[#1b365d] bg-blue-50/40'
                        : 'border-slate-200 hover:border-slate-300 bg-white'
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
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-bold text-sm text-slate-900">{doc.name}</span>
                        {doc.recommended && (
                          <span className="px-2 py-0.5 text-[10px] font-semibold bg-emerald-100 text-emerald-800 rounded">
                            Recommended
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-slate-600 mt-1 leading-relaxed">{doc.reason}</p>
                      <div className="mt-2 text-[11px] font-mono text-slate-600 bg-slate-100/90 px-2.5 py-1 rounded-lg inline-block border border-slate-200">
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
                  className="mt-0.5 h-4 w-4 rounded border-slate-300 text-[#1b365d] focus:ring-[#1b365d]"
                />
                <label htmlFor="acceptRefNumbers" className="text-xs sm:text-sm font-semibold text-slate-800 cursor-pointer">
                  I accept the suggested reference numbers for the selected documents.
                </label>
              </div>
              <p className="text-[11px] text-slate-500 pl-6 leading-relaxed">
                Official reference numbers are safely allocated in unbroken sequence only when you generate.
              </p>
            </div>
          </div>

          {/* 3. Grouped Missing Details Questions */}
          {missingQuestions.length > 0 && (
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-5 sm:p-6 space-y-4">
              <div className="border-b border-slate-100 pb-3">
                <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
                  <HelpCircle className="w-5 h-5 text-amber-600" />
                  Additional details needed
                </h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  Please answer these questions so the official documents can be completed accurately.
                </p>
              </div>

              <div className="space-y-4">
                {missingQuestions.map((q) => {
                  const val = answers[q.key] ?? '';
                  return (
                    <div key={q.key} className="space-y-1.5">
                      <label className="block text-xs sm:text-sm font-semibold text-slate-800">
                        {q.question} {q.required && <span className="text-red-500">*</span>}
                      </label>
                      <p className="text-[11px] text-slate-400">Needed for: {q.needed_by.join(', ')}</p>

                      {/* Widget rendering based on type */}
                      {q.type === 'enum' && q.values ? (
                        <select
                          value={val}
                          onChange={(e) => setAnswers({ ...answers, [q.key]: e.target.value })}
                          className="w-full text-xs sm:text-sm bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:bg-white focus:outline-none focus:ring-1 focus:ring-[#1b365d]"
                        >
                          {q.values.map((opt) => (
                            <option key={opt} value={opt}>{opt}</option>
                          ))}
                        </select>
                      ) : q.type === 'time' ? (
                        <input
                          type="time"
                          value={val}
                          onChange={(e) => setAnswers({ ...answers, [q.key]: e.target.value })}
                          className="w-full text-xs sm:text-sm bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:bg-white focus:outline-none focus:ring-1 focus:ring-[#1b365d]"
                        />
                      ) : q.type === 'date' ? (
                        <input
                          type="date"
                          value={val}
                          onChange={(e) => setAnswers({ ...answers, [q.key]: e.target.value })}
                          className="w-full text-xs sm:text-sm bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:bg-white focus:outline-none focus:ring-1 focus:ring-[#1b365d]"
                        />
                      ) : q.type === 'int' ? (
                        <input
                          type="number"
                          min="0"
                          step="1"
                          value={val}
                          onChange={(e) => setAnswers({ ...answers, [q.key]: e.target.value })}
                          className="w-full text-xs sm:text-sm bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:bg-white focus:outline-none focus:ring-1 focus:ring-[#1b365d]"
                        />
                      ) : q.type === 'money' ? (
                        <input
                          type="number"
                          min="0"
                          step="0.01"
                          value={val}
                          onChange={(e) => setAnswers({ ...answers, [q.key]: e.target.value })}
                          className="w-full text-xs sm:text-sm bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:bg-white focus:outline-none focus:ring-1 focus:ring-[#1b365d]"
                        />
                      ) : q.type === 'longtext' ? (
                        <textarea
                          rows={2}
                          value={val}
                          onChange={(e) => setAnswers({ ...answers, [q.key]: e.target.value })}
                          className="w-full text-xs sm:text-sm bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:bg-white focus:outline-none focus:ring-1 focus:ring-[#1b365d]"
                        />
                      ) : (
                        <div>
                          <input
                            type="text"
                            value={val}
                            onChange={(e) => setAnswers({ ...answers, [q.key]: e.target.value })}
                            placeholder={
                              q.key === 'budget_items'
                                ? 'e.g. 1100 or Banner: 800, Snacks: 300'
                                : q.key === 'judges'
                                ? 'e.g. Dr. Alok Kumar, Prof. Sharma (or leave blank if none)'
                                : q.label
                            }
                            className="w-full text-xs sm:text-sm bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:bg-white focus:outline-none focus:ring-1 focus:ring-[#1b365d]"
                          />
                          {q.key === 'budget_items' && (
                            <p className="text-[10px] text-slate-400 mt-1">
                              Enter a total amount (e.g. 1100) or comma-separated items with costs.
                            </p>
                          )}
                          {q.key === 'judges' && (
                            <p className="text-[10px] text-slate-400 mt-1">
                              Enter comma-separated names of external judges, or leave empty if none.
                            </p>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
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
            <button
              type="button"
              onClick={handleGenerate}
              disabled={generating || selectedTemplateIds.length === 0 || !refNumbersAccepted || Boolean(hasUnconfirmedDraft)}
              className="w-full sm:w-auto px-6 py-3 bg-[#1b365d] hover:bg-[#132742] text-white font-bold text-sm rounded-xl shadow-md flex items-center justify-center gap-2 disabled:opacity-50 transition-all cursor-pointer disabled:cursor-not-allowed"
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
      )}
    </div>
  );
};
