import React, { useState, useEffect, useRef } from 'react';
import {
  Sparkles,
  ArrowRight,
  ChevronDown,
  ChevronUp,
  FileText,
  Award,
  Users,
  Receipt,
  Megaphone,
  ClipboardList,
  AlertCircle,
  Loader2,
  Table2,
  X,
} from 'lucide-react';
import { api } from '../api/client';
import { BatchRowsPanel, BatchRows } from './BatchRowsPanel';
import { HomeCreateResponse, HomeGenerateResponse } from '../types';

interface HomePageProps {
  clubId: string | number;
  initialTemplateId?: string | null;
  initialPrompt?: string | null;
  initialText?: string;
  onDocumentsGenerated: (result: HomeCreateResponse | HomeGenerateResponse) => void;
}

const EXAMPLE_REQUESTS = [
  {
    label: 'Web Dev Workshop (2 days)',
    text: 'We are conducting a two-day Web Development Workshop on 14–15 October in Seminar Hall for around 120 students',
  },
  {
    label: 'Quiz winner certificate',
    text: 'certificate for the winner of our quiz, Riya Patel, 1st place',
  },
  {
    label: 'Core committee meeting minutes',
    text: "minutes of today's core committee meeting",
  },
  {
    label: 'Band audition notice',
    text: 'notice about auditions for our music band next Friday',
  },
];

type TemplateOption = {
  key: string;
  name: string;
  description?: string;
  category?: string;
  is_system: boolean;
};

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
  const [inputText, setInputText] = useState(initialText || initialPrompt || '');
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(initialTemplateId || null);
  const [showTypePicker, setShowTypePicker] = useState(false);
  const [templateOptions, setTemplateOptions] = useState<TemplateOption[]>([]);
  const [batchRows, setBatchRows] = useState<BatchRows | null>(null);
  const [showSpreadsheetImport, setShowSpreadsheetImport] = useState(false);

  const [creating, setCreating] = useState(false);
  const [progressStage, setProgressStage] = useState<string>('Reading your request…');
  const [error, setError] = useState<string | null>(null);

  const textAreaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (clubId) {
      api.documents
        .listTemplates(clubId)
        .then((data) =>
          setTemplateOptions(
            (data || [])
              .filter((t: any) => t.status === 'published')
              .map((t: any) => ({
                key: t.slug || t.id,
                name: t.name,
                description: t.description,
                category: t.category,
                is_system: !!t.is_system,
              }))
              .sort(
                (x: TemplateOption, y: TemplateOption) =>
                  Number(x.is_system) - Number(y.is_system) || x.name.localeCompare(y.name)
              )
          )
        )
        .catch(() => setTemplateOptions([]));
    }
  }, [clubId]);

  useEffect(() => {
    if (initialTemplateId) {
      setSelectedTemplateId(initialTemplateId);
    }
    if (initialPrompt) {
      setInputText(initialPrompt);
    }
  }, [initialTemplateId, initialPrompt]);

  const handleChipClick = (text: string) => {
    setInputText(text);
    setError(null);
    textAreaRef.current?.focus();
  };

  const handleCreate = async () => {
    // If spreadsheet rows are loaded, generate from batch rows
    if (batchRows && batchRows.rows.length > 0) {
      setCreating(true);
      setProgressStage('Generating documents from spreadsheet rows…');
      setError(null);
      try {
        const eventData: Record<string, any> = {
          rows: batchRows.rows,
          rows_for: batchRows.templateKey,
        };
        const response = await api.home.generate(clubId, {
          selected_template_ids: [batchRows.templateKey],
          event_data: eventData,
          ref_numbers_accepted: true,
          allow_blanks: true,
        });
        onDocumentsGenerated(response);
      } catch (err: any) {
        setError(err?.detail?.message || err?.message || 'Failed to generate batch documents.');
      } finally {
        setCreating(false);
      }
      return;
    }

    if (!inputText.trim()) {
      setError('Please describe what document or event you need.');
      return;
    }

    setCreating(true);
    setError(null);
    setProgressStage('Reading your request and extracting details…');

    const timer1 = setTimeout(() => {
      setProgressStage('Applying club settings and deciding document set…');
    }, 2500);

    const timer2 = setTimeout(() => {
      setProgressStage('Drafting official documents with clean blanks…');
    }, 6000);

    try {
      const response = await api.home.create(clubId, {
        text: inputText.trim(),
        selected_template_id: selectedTemplateId || undefined,
      });
      onDocumentsGenerated(response);
    } catch (err: any) {
      let msg = 'Could not create documents. Please try again.';
      if (typeof err?.detail === 'string') {
        msg = err.detail;
      } else if (err?.detail?.message) {
        msg = err.detail.message;
      } else if (err?.message) {
        msg = err.message;
      }
      setError(msg);
    } finally {
      clearTimeout(timer1);
      clearTimeout(timer2);
      setCreating(false);
    }
  };

  const selectedTemplate = templateOptions.find((t) => t.key === selectedTemplateId);

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 py-8 sm:py-12 space-y-6">
      {/* Title & Introduction */}
      <div className="text-center space-y-2">
        <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
          Create Documents
        </h1>
        <p className="text-sm sm:text-base text-slate-600 max-w-xl mx-auto">
          Describe what you need in plain language. AI drafts the official SVNIT documents immediately,
          using your club's letterhead, signatories, and venues.
        </p>
      </div>

      {/* Main Request Card */}
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 sm:p-8 space-y-5">
        <div>
          <label htmlFor="create-prompt" className="block text-sm font-bold text-slate-800 mb-2">
            What do you want to create?
          </label>
          <div className="relative">
            <textarea
              id="create-prompt"
              ref={textAreaRef}
              rows={4}
              value={inputText}
              onChange={(e) => {
                setInputText(e.target.value);
                if (error) setError(null);
              }}
              placeholder="e.g. We are conducting a two-day Web Development Workshop on 14–15 October in Seminar Hall for around 120 students"
              className="w-full text-sm sm:text-base bg-slate-50 border border-slate-200 rounded-xl p-4 text-slate-900 placeholder-slate-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand-700 focus:border-transparent transition-all resize-y"
              disabled={creating}
            />
          </div>
        </div>

        {/* Quick Example Chips */}
        <div className="space-y-1.5">
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
            Sample requests:
          </span>
          <div className="flex flex-wrap gap-2">
            {EXAMPLE_REQUESTS.map((ex) => (
              <button
                key={ex.label}
                type="button"
                onClick={() => handleChipClick(ex.text)}
                disabled={creating}
                className="text-xs bg-slate-100 hover:bg-slate-200 text-slate-700 px-3 py-1.5 rounded-lg font-medium transition-colors border border-slate-200/60 text-left"
              >
                {ex.label}
              </button>
            ))}
          </div>
        </div>

        {/* Optional Document Type Picker (Collapsed by Default) */}
        <div className="pt-2 border-t border-slate-100">
          <div className="flex items-center justify-between">
            <button
              type="button"
              onClick={() => setShowTypePicker(!showTypePicker)}
              className="text-xs font-semibold text-slate-600 hover:text-brand-700 flex items-center gap-1.5 transition-colors py-1"
            >
              {showTypePicker ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              <span>Choose document type (optional)</span>
            </button>

            {selectedTemplate && (
              <div className="flex items-center gap-1.5 text-xs font-medium bg-brand-50 text-brand-800 px-2.5 py-1 rounded-full border border-brand-200">
                <span>Generating only: <strong>{selectedTemplate.name}</strong></span>
                <button
                  type="button"
                  onClick={() => setSelectedTemplateId(null)}
                  className="hover:text-red-600 ml-1"
                  title="Clear document type filter"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            )}
          </div>

          {showTypePicker && (
            <div className="mt-3 p-4 bg-slate-50 rounded-xl border border-slate-200 space-y-3">
              <p className="text-xs text-slate-500">
                By default, the AI automatically selects the right document set for your sentence (e.g.
                Permission Letter + Event Proposal for events). Pick a specific document below if you want
                only that one.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
                {templateOptions.map((t) => {
                  const Icon = templateIcon(t);
                  const isSelected = selectedTemplateId === t.key;
                  return (
                    <button
                      key={t.key}
                      type="button"
                      onClick={() => setSelectedTemplateId(isSelected ? null : t.key)}
                      className={`p-2.5 rounded-lg border text-left flex items-start gap-2.5 transition-all text-xs ${
                        isSelected
                          ? 'bg-brand-50 border-brand-700 ring-1 ring-brand-700 text-brand-900 font-semibold'
                          : 'bg-white border-slate-200 hover:border-slate-300 text-slate-800'
                      }`}
                    >
                      <Icon className={`w-4 h-4 shrink-0 mt-0.5 ${isSelected ? 'text-brand-700' : 'text-slate-400'}`} />
                      <div className="min-w-0">
                        <div className="truncate font-medium">{t.name}</div>
                        {t.description && (
                          <div className="text-[11px] text-slate-500 line-clamp-1">{t.description}</div>
                        )}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* Optional Spreadsheet Import */}
        <div className="pt-2 border-t border-slate-100">
          <button
            type="button"
            onClick={() => setShowSpreadsheetImport(!showSpreadsheetImport)}
            className="text-xs font-semibold text-slate-500 hover:text-slate-800 flex items-center gap-1.5 transition-colors"
          >
            <Table2 className="w-3.5 h-3.5" />
            <span>{showSpreadsheetImport ? 'Hide spreadsheet batch import' : 'Need certificates or receipts for a whole list? Import from CSV / Google Sheets'}</span>
          </button>

          {showSpreadsheetImport && (
            <div className="mt-3">
              <BatchRowsPanel
                clubId={clubId}
                templates={templateOptions}
                value={batchRows}
                onChange={setBatchRows}
              />
            </div>
          )}
        </div>

        {/* Inline Error Message */}
        {error && (
          <div className="p-3.5 bg-red-50 border border-red-200 rounded-xl flex items-start gap-2.5 text-xs sm:text-sm text-red-800 animate-in fade-in">
            <AlertCircle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
            <div className="flex-1">{error}</div>
            <button
              type="button"
              onClick={() => setError(null)}
              className="text-red-500 hover:text-red-800"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Progress Display */}
        {creating && (
          <div className="p-4 bg-brand-50 border border-brand-200 rounded-xl flex items-center gap-3 animate-pulse">
            <Loader2 className="w-5 h-5 text-brand-700 animate-spin shrink-0" />
            <div className="space-y-0.5">
              <p className="text-xs sm:text-sm font-bold text-brand-900">{progressStage}</p>
              <p className="text-[11px] text-brand-700">
                Drafting official documents with clean blanks where details were not specified…
              </p>
            </div>
          </div>
        )}

        {/* Action Button */}
        <div className="pt-2 flex flex-col sm:flex-row items-center justify-between gap-3">
          <p className="text-xs text-slate-500">
            Unstated details will be left as clean blank lines (`__________`) for you to review and edit.
          </p>

          <button
            type="button"
            onClick={handleCreate}
            disabled={creating || (!inputText.trim() && !batchRows)}
            className="w-full sm:w-auto px-6 py-3 bg-brand-700 hover:bg-brand-800 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-bold rounded-xl shadow-sm flex items-center justify-center gap-2 transition-all"
          >
            {creating ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Creating…</span>
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" />
                <span>Create Documents</span>
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
