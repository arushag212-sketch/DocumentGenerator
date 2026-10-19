import React, { useState } from 'react';
import { Sparkles, Wand2, ArrowRight, Check, X, Loader2 } from 'lucide-react';
import { api } from '../api/client';

interface TemplateWizardModalProps {
  clubId: string | number;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (templateId: string) => void;
}

interface Question {
  id: string;
  question: string;
  category: string;
  options: string[];
}

export const TemplateWizardModal: React.FC<TemplateWizardModalProps> = ({
  clubId,
  isOpen,
  onClose,
  onSuccess,
}) => {
  const [step, setStep] = useState<'prompt' | 'questions' | 'generating'>('prompt');
  const [prompt, setPrompt] = useState('');
  const [questions, setQuestions] = useState<Question[]>([]);
  const [suggestedTitle, setSuggestedTitle] = useState('');
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleFetchQuestions = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.documents.getWizardQuestions(clubId, prompt.trim());
      setQuestions(res.questions || []);
      setSuggestedTitle(res.suggested_title || '');
      // Auto-select first option for each question as default
      const initialAnswers: Record<string, string> = {};
      res.questions.forEach((q) => {
        if (q.options.length > 0) initialAnswers[q.id] = q.options[0];
      });
      setAnswers(initialAnswers);
      setStep('questions');
    } catch (err: any) {
      setError(err.message || 'Failed to retrieve clarifying questions.');
    } finally {
      setLoading(false);
    }
  };

  const handleGenerate = async () => {
    setLoading(true);
    setError(null);
    setStep('generating');
    try {
      const res = await api.documents.generateFromWizard(clubId, {
        prompt: prompt.trim(),
        answers,
      });
      onSuccess(res.template.id);
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to generate template from wizard.');
      setStep('questions');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in">
      <div className="bg-white rounded-2xl shadow-2xl max-w-xl w-full overflow-hidden flex flex-col border border-slate-200">
        {/* Header */}
        <div className="px-6 py-4 bg-gradient-to-r from-indigo-50 to-purple-50 border-b border-indigo-100 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-2 bg-indigo-600 text-white rounded-xl shadow-xs">
              <Wand2 className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-bold text-slate-800 text-base">Template Creation Wizard</h3>
              <p className="text-xs text-slate-500">
                {step === 'prompt' ? 'Step 1 of 2: Describe your document' : 'Step 2 of 2: Refine details & design'}
              </p>
            </div>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 p-1">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-5">
          {error && (
            <div className="p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-xl flex items-center justify-between">
              <span>{error}</span>
              <button onClick={() => setError(null)} className="text-red-400 hover:text-red-600">
                <X className="w-4 h-4" />
              </button>
            </div>
          )}

          {step === 'prompt' && (
            <form onSubmit={handleFetchQuestions} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-2">
                  What kind of document do you want to create?
                </label>
                <textarea
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="e.g. An approval note for our annual coding hackathon with a budget breakdown and coordinator signatures..."
                  rows={4}
                  required
                  className="w-full text-xs p-3 bg-slate-50 border border-slate-300 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:bg-white focus:outline-none"
                />
              </div>

              {/* Quick suggestions */}
              <div>
                <span className="block text-[11px] font-medium text-slate-500 mb-1.5">Or choose a common type:</span>
                <div className="flex flex-wrap gap-1.5">
                  {[
                    'Lab & Hall Booking Permission',
                    'Hackathon Financial Sanction Note',
                    'Guest Lecture Honorarium Request',
                    'Annual Club Activity Summary Report',
                  ].map((preset) => (
                    <button
                      key={preset}
                      type="button"
                      onClick={() => setPrompt(preset)}
                      className="text-[11px] px-2.5 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg transition"
                    >
                      {preset}
                    </button>
                  ))}
                </div>
              </div>

              <div className="pt-2 flex justify-end">
                <button
                  type="submit"
                  disabled={loading || !prompt.trim()}
                  className="flex items-center gap-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-xs font-bold rounded-xl shadow-sm transition"
                >
                  {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                  <span>Continue to Customization</span>
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            </form>
          )}

          {step === 'questions' && (
            <div className="space-y-5">
              {suggestedTitle && (
                <div className="p-3 bg-indigo-50/70 border border-indigo-200 rounded-xl flex items-center gap-2">
                  <span className="text-xs text-indigo-700 font-semibold">Suggested Title:</span>
                  <span className="text-xs text-slate-800 font-bold">{suggestedTitle}</span>
                </div>
              )}

              <div className="space-y-4 max-h-[50vh] overflow-y-auto pr-1">
                {questions.map((q) => (
                  <div key={q.id} className="space-y-2">
                    <label className="block text-xs font-semibold text-slate-800">{q.question}</label>
                    <div className="grid grid-cols-2 gap-2">
                      {q.options.map((opt) => {
                        const isSelected = answers[q.id] === opt;
                        return (
                          <button
                            key={opt}
                            type="button"
                            onClick={() => setAnswers((prev) => ({ ...prev, [q.id]: opt }))}
                            className={`p-2.5 rounded-xl border text-left text-xs transition flex items-center justify-between ${
                              isSelected
                                ? 'border-indigo-600 bg-indigo-50/80 font-bold text-indigo-900 ring-2 ring-indigo-500/20'
                                : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300'
                            }`}
                          >
                            <span className="truncate pr-1">{opt}</span>
                            {isSelected && <Check className="w-4 h-4 text-indigo-600 shrink-0" />}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>

              <div className="pt-3 border-t border-slate-200 flex items-center justify-between">
                <button
                  type="button"
                  onClick={() => setStep('prompt')}
                  className="px-4 py-2 text-xs font-medium text-slate-600 hover:text-slate-800 rounded-xl"
                >
                  Back
                </button>
                <button
                  type="button"
                  onClick={handleGenerate}
                  disabled={loading}
                  className="flex items-center gap-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-xl shadow-md transition"
                >
                  {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Wand2 className="w-4 h-4" />}
                  <span>Build My Template</span>
                </button>
              </div>
            </div>
          )}

          {step === 'generating' && (
            <div className="py-12 flex flex-col items-center justify-center text-center space-y-4">
              <Loader2 className="w-10 h-10 text-indigo-600 animate-spin" />
              <div>
                <h4 className="font-bold text-slate-800 text-sm">Designing your custom document template...</h4>
                <p className="text-xs text-slate-500 mt-1">
                  Synthesizing fields, formatting tables, laying out signatures, and styling theme.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
