import React, { useState, useEffect } from 'react';
import {
  Copy,
  PlusCircle,
  RefreshCw,
  Loader2,
  CheckCircle,
  AlertCircle,
  Tag,
  Hash,
  Shield,
  Layers,
  Sparkles,
  Edit2,
  Archive,
  FileText,
  X,
  Wand2,
  Upload,
} from 'lucide-react';
import { api } from '../api/client';
import { TemplateGalleryItem, ClubPermissions } from '../types';
import { TemplateWizardModal } from './TemplateWizardModal';
import { TemplateImportModal } from './TemplateImportModal';

interface TemplateGalleryTabProps {
  clubId: string | number;
  permissions: ClubPermissions | null;
  onSelectTemplate: (templateId: string) => void;
  onOpenEditor?: (templateId: string) => void;
}

const AI_TEMPLATE_EXAMPLES: { label: string; prompt: string }[] = [
  {
    label: 'Sponsorship Request',
    prompt: 'A sponsorship request letter to a company with event name, date, venue, a tiers table with an amount per tier, and signatures for the coordinator and the faculty advisor',
  },
  {
    label: 'Meeting Attendance Sheet',
    prompt: 'A meeting attendance sheet with event name, date, venue, a table of attendees with roll number, name and signature, and signatures for the coordinator and faculty advisor',
  },
  {
    label: 'Participation Certificate',
    prompt: 'A certificate of participation with participant name, event name, dates and organising club, using the club logo at the top and signatures for the student head and faculty advisor',
  },
  {
    label: 'Equipment Gate Pass',
    prompt: 'A letter to the Chief Security Officer requesting a gate pass to take equipment off campus, with purpose, dates, a table of items with quantity and serial number, and signatures for the coordinator and faculty advisor',
  },
  {
    label: 'Volunteer Thank-you Letter',
    prompt: 'A thank-you letter to event volunteers with volunteer name, event name, date, a short paragraph on their contribution, and the student head signature',
  },
];

export const TemplateGalleryTab: React.FC<TemplateGalleryTabProps> = ({
  clubId,
  permissions,
  onSelectTemplate,
  onOpenEditor,
}) => {
  const [templates, setTemplates] = useState<TemplateGalleryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [lastCreatedId, setLastCreatedId] = useState<string | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string>('All');

  // Unified Action Modal state
  const [actionModal, setActionModal] = useState<{
    type: 'blank' | 'fork' | 'rename' | 'archive';
    tmpl?: TemplateGalleryItem;
    value?: string;
  } | null>(null);
  const [modalSubmitting, setModalSubmitting] = useState<boolean>(false);
  const [modalError, setModalError] = useState<string | null>(null);

  // AI Describe state
  const [aiPrompt, setAiPrompt] = useState<string>('');
  const [submittingAi, setSubmittingAi] = useState<boolean>(false);
  const [aiError, setAiError] = useState<string | null>(null);
  const [aiCreatedTemplate, setAiCreatedTemplate] = useState<{ id: string; name: string; slug: string } | null>(null);
  const [ambiguousLogoModal, setAmbiguousLogoModal] = useState<{
    candidates: any[];
    templateId: string;
  } | null>(null);

  // Wizard & Import state
  const [showWizardModal, setShowWizardModal] = useState<boolean>(false);
  const [showImportModal, setShowImportModal] = useState<boolean>(false);

  const handleAiDraftSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!aiPrompt.trim()) return;
    try {
      setSubmittingAi(true);
      setAiError(null);
      setError(null);
      const res = await api.documents.aiDraftTemplate(clubId, {
        description: aiPrompt.trim(),
      });
      await fetchTemplates();
      if (res.logo_resolution && res.logo_resolution.status === 'ambiguous') {
        setAmbiguousLogoModal({
          candidates: res.logo_resolution.candidates || [],
          templateId: res.template.id,
        });
      } else {
        setAiCreatedTemplate({
          id: res.template.id,
          name: res.template.name,
          slug: res.template.slug || res.template.id,
        });
        setSuccessMsg(`AI draft created for "${res.template.name}"!`);
      }
    } catch (err: any) {
      setAiError(err.message || 'Failed to generate AI template draft.');
    } finally {
      setSubmittingAi(false);
    }
  };

  const handlePickLogo = (_assetId: string) => {
    if (!ambiguousLogoModal) return;
    const tmplId = ambiguousLogoModal.templateId;
    setAmbiguousLogoModal(null);
    if (onOpenEditor) {
      onOpenEditor(tmplId);
    }
  };

  const fetchTemplates = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.documents.listTemplates(clubId);
      setTemplates(data || []);
    } catch (err: any) {
      setError(err.message || 'Failed to load templates');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTemplates();
  }, [clubId]);

  const handleModalSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!actionModal) return;
    try {
      setModalSubmitting(true);
      setModalError(null);
      setError(null);
      const val = (actionModal.value || '').trim();
      if (actionModal.type === 'blank') {
        if (!val) return;
        const res = await api.documents.createBlankTemplate(clubId, { name: val, category: 'Official Event Documents' });
        setActionModal(null);
        await fetchTemplates();
        if (onOpenEditor) onOpenEditor(res.id);
        else setSuccessMsg(`Created new blank template "${res.name}".`);
      } else if (actionModal.type === 'fork' && actionModal.tmpl) {
        const res = await api.documents.forkTemplate(clubId, actionModal.tmpl.id, { name: val || undefined });
        setSuccessMsg(`Forked "${actionModal.tmpl.name}" as "${res.name}"!`);
        setLastCreatedId(res.id);
        setActionModal(null);
        await fetchTemplates();
        if (onOpenEditor) onOpenEditor(res.id);
      } else if (actionModal.type === 'rename' && actionModal.tmpl) {
        if (!val) return;
        const res = await api.documents.updateTemplate(clubId, actionModal.tmpl.id, { name: val });
        setSuccessMsg(`Template renamed to "${res.name}".`);
        setActionModal(null);
        await fetchTemplates();
      } else if (actionModal.type === 'archive' && actionModal.tmpl) {
        await api.documents.deleteTemplate(clubId, actionModal.tmpl.id);
        setSuccessMsg(`Template "${actionModal.tmpl.name}" archived successfully.`);
        setActionModal(null);
        await fetchTemplates();
      }
    } catch (err: any) {
      setModalError(err.message || 'Operation failed');
    } finally {
      setModalSubmitting(false);
    }
  };

  const categories = ['All', 'Official Event Documents', 'Custom Drafts', 'pre_event', 'post_event', 'meeting'];

  const filteredTemplates = templates.filter((t) => {
    if (selectedCategory === 'All') return true;
    if (selectedCategory === 'Custom Drafts') return !t.is_system;
    if (selectedCategory === 'Official Event Documents') return t.is_system;
    return t.stage === selectedCategory;
  });

  const canManage = Boolean(permissions?.can_create_documents);

  if (loading) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-12 text-center shadow-sm">
        <Loader2 className="w-8 h-8 text-[#1b365d] animate-spin mx-auto mb-3" />
        <p className="text-slate-600 text-sm font-medium">Loading Template Gallery...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <Layers className="w-6 h-6 text-[#1b365d]" />
            <h1 className="text-xl font-bold text-slate-900">Template Gallery</h1>
            <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200">
              {templates.length} templates
            </span>
          </div>
          <p className="text-xs text-slate-600 mt-1.5 max-w-2xl">
            Official institute-standard document templates and club-customized workflows. System templates are immutable and read-only; club editors and admins can customize them by creating an independent club fork.
          </p>
        </div>

        <div className="flex items-center gap-2 self-start md:self-auto">
          {canManage && onOpenEditor && (
            <>
              <button
                type="button"
                data-testid="wizard-template-btn"
                onClick={() => setShowWizardModal(true)}
                className="inline-flex items-center gap-1.5 text-xs text-white bg-indigo-600 hover:bg-indigo-700 px-3 py-1.5 rounded-lg font-semibold shadow-xs transition-colors"
              >
                <Wand2 className="w-3.5 h-3.5" />
                Template Wizard
              </button>

              <button
                type="button"
                data-testid="import-template-btn"
                onClick={() => setShowImportModal(true)}
                className="inline-flex items-center gap-1.5 text-xs text-slate-700 bg-white border border-slate-300 hover:bg-slate-50 px-3 py-1.5 rounded-lg font-semibold shadow-xs transition-colors"
              >
                <Upload className="w-3.5 h-3.5 text-blue-600" />
                Import Document
              </button>

              <button
                type="button"
                data-testid="new-blank-template-btn"
                onClick={() => setActionModal({ type: 'blank', value: '' })}
                className="inline-flex items-center gap-1.5 text-xs text-white bg-blue-600 hover:bg-blue-700 px-3 py-1.5 rounded-lg font-semibold shadow-xs transition-colors"
              >
                <PlusCircle className="w-3.5 h-3.5" />
                New Blank Template
              </button>
            </>
          )}

          <button
            onClick={fetchTemplates}
            className="inline-flex items-center gap-1.5 text-xs text-slate-600 bg-slate-100 hover:bg-slate-200 px-3 py-1.5 rounded-lg font-semibold transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </button>
        </div>
      </div>

      {/* Describe your template (AI Draft) - Admin/Editor Only */}
      {canManage && onOpenEditor && (
        <div data-testid="ai-describe-box" className="bg-gradient-to-r from-blue-900 to-[#1b365d] rounded-xl p-5 text-white shadow-md border border-blue-800">
          <div className="flex items-center justify-between gap-4 mb-2">
            <div className="flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-yellow-300" />
              <h2 className="text-sm font-bold tracking-wide uppercase text-blue-100">Describe Your Template (AI Draft)</h2>
              <span className="text-[10px] bg-blue-700/80 text-blue-100 px-2 py-0.5 rounded-full font-semibold">Admin & Editor</span>
            </div>
            <span className="text-xs text-blue-200 hidden sm:inline">Builds a draft directly in the TipTap editor</span>
          </div>
          <p className="text-xs text-blue-100 mb-3">
            Type what you need in plain English (e.g. purpose, event fields, repeating tables with computed totals, signees, and logos like &quot;use the ACM logo on the left&quot;).
          </p>
          <form onSubmit={handleAiDraftSubmit} className="space-y-3">
            <textarea
              data-testid="ai-describe-input"
              value={aiPrompt}
              onChange={(e) => setAiPrompt(e.target.value)}
              placeholder="e.g. A sponsorship request letter to a company with event name, date, venue, a tiers table with an amount per tier, and signatures for the coordinator and the faculty advisor"
              rows={3}
              className="w-full text-xs text-slate-900 bg-white rounded-lg p-3 border border-blue-300 focus:outline-none focus:ring-2 focus:ring-yellow-400 font-normal shadow-inner placeholder:text-slate-400"
              disabled={submittingAi}
            />
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-1.5 flex-wrap">
                <span className="text-[11px] text-blue-200">Examples:</span>
                {AI_TEMPLATE_EXAMPLES.map((ex) => (
                  <button
                    key={ex.label}
                    type="button"
                    onClick={() => setAiPrompt(ex.prompt)}
                    className="text-[11px] bg-blue-800/80 hover:bg-blue-700 text-blue-100 px-2 py-0.5 rounded transition-colors"
                  >
                    {ex.label}
                  </button>
                ))}
              </div>
              <button
                type="submit"
                disabled={submittingAi || !aiPrompt.trim()}
                data-testid="ai-draft-submit-btn"
                className="inline-flex items-center gap-2 px-4 py-2 bg-yellow-400 hover:bg-yellow-300 text-slate-900 text-xs font-bold rounded-lg shadow-sm transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {submittingAi ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Drafting Template...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-3.5 h-3.5 text-blue-950" />
                    <span>Generate Draft Template →</span>
                  </>
                )}
              </button>
            </div>
            {submittingAi && (
              <p className="text-[11px] text-blue-200" role="status">
                The AI is designing fields, tables and signatories. This can take up to a minute when the model is busy.
              </p>
            )}
          </form>
          {aiError && (
            <div className="mt-3 p-3 bg-red-900/60 border border-red-500 rounded-lg text-xs text-red-100 flex flex-col gap-1.5">
              <div className="flex items-center gap-2">
                <AlertCircle className="w-4 h-4 flex-shrink-0 text-red-300" />
                <span>{aiError}</span>
              </div>
              {(aiError.toLowerCase().includes('session') || aiError.toLowerCase().includes('credential') || aiError.toLowerCase().includes('unauthorized')) && (
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pl-6 mt-1">
                  <p className="text-[11px] text-amber-200">
                    Your login session has expired. Please sign in again to continue drafting templates.
                  </p>
                  <button
                    type="button"
                    onClick={() => window.location.reload()}
                    className="inline-flex items-center gap-1.5 px-3 py-1 bg-yellow-400 hover:bg-yellow-300 text-slate-900 font-bold rounded-lg text-xs shadow-xs transition-colors self-start sm:self-auto"
                  >
                    <span>Sign In Again →</span>
                  </button>
                </div>
              )}
              {(aiError.toLowerCase().includes('gemini') || aiError.toLowerCase().includes('api key') || aiError.toLowerCase().includes('unavailable') || aiError.toLowerCase().includes('quota')) && (
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pl-6 mt-1">
                  <p className="text-[11px] text-amber-200">
                    Tip: Set <code className="bg-blue-950 px-1 py-0.5 rounded text-yellow-300 font-mono">GEMINI_API_KEY</code> in <code className="bg-blue-950 px-1 py-0.5 rounded text-yellow-300 font-mono">.env</code> to activate live Gemini AI drafting.
                  </p>
                  <button
                    type="button"
                    onClick={() => setActionModal({ type: 'blank', value: '' })}
                    className="inline-flex items-center gap-1.5 px-3 py-1 bg-amber-400 hover:bg-amber-300 text-slate-900 font-bold rounded-lg text-xs shadow-xs transition-colors self-start sm:self-auto"
                  >
                    <span>Open Manual Editor →</span>
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {aiCreatedTemplate && (
        <div className="p-4 bg-emerald-50 border border-emerald-300 rounded-xl flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-xs">
          <div className="flex items-center gap-2.5">
            <CheckCircle className="w-5 h-5 text-emerald-600 flex-shrink-0" />
            <div>
              <p className="text-xs sm:text-sm font-bold text-emerald-950">
                Template Ready: &quot;{aiCreatedTemplate.name}&quot;
              </p>
              <p className="text-xs text-emerald-700">
                Generated from your description. You can now use it on Home to generate documents immediately!
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => onSelectTemplate(aiCreatedTemplate.slug || aiCreatedTemplate.id)}
              className="px-3.5 py-1.5 bg-[#1b365d] hover:bg-[#132742] text-white text-xs font-bold rounded-lg shadow-sm flex items-center gap-1.5 transition-colors"
            >
              <Sparkles className="w-3.5 h-3.5 text-amber-300" />
              Use This Template
            </button>
            {onOpenEditor && (
              <button
                type="button"
                onClick={() => onOpenEditor(aiCreatedTemplate.id)}
                className="px-3 py-1.5 bg-white hover:bg-slate-100 text-slate-700 text-xs font-semibold rounded-lg border border-slate-300 transition-colors"
              >
                Customize in Editor
              </button>
            )}
          </div>
        </div>
      )}

      {successMsg && !aiCreatedTemplate && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-xs sm:text-sm text-emerald-800 flex items-center justify-between font-medium">
          <div className="flex items-center gap-2">
            <CheckCircle className="w-4 h-4 flex-shrink-0 text-emerald-600" />
            <span>{successMsg}</span>
          </div>
          {lastCreatedId && onOpenEditor && (
            <button
              onClick={() => onOpenEditor(lastCreatedId)}
              className="ml-3 px-3 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-bold transition-colors shadow-xs"
            >
              Open in Editor →
            </button>
          )}
        </div>
      )}

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-xs sm:text-sm text-red-800 flex items-center gap-2 font-medium">
          <AlertCircle className="w-4 h-4 flex-shrink-0 text-red-600" />
          <span>{error}</span>
        </div>
      )}

      {/* Filter Tabs */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1">
        {categories.map((cat) => (
          <button
            key={cat}
            onClick={() => setSelectedCategory(cat)}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all whitespace-nowrap ${
              selectedCategory === cat
                ? 'bg-[#1b365d] text-white shadow-sm'
                : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
            }`}
          >
            {cat === 'pre_event' ? 'Pre-Event' : cat === 'post_event' ? 'Post-Event' : cat === 'meeting' ? 'Meetings' : cat}
          </button>
        ))}
      </div>

      {/* Templates Grid & Empty State */}
      {filteredTemplates.length === 0 ? (
        <div className="bg-white rounded-xl border border-dashed border-slate-300 p-12 text-center">
          <Layers className="w-12 h-12 text-slate-300 mx-auto mb-3" />
          <h3 className="text-base font-semibold text-slate-700">No templates found</h3>
          <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
            {selectedCategory === 'Custom Drafts'
              ? 'No custom drafts yet. Use "Customize (fork)" on any system template to create an independent club draft.'
              : 'No templates match the selected filter.'}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredTemplates.map((tmpl) => (
            <div
              key={tmpl.id}
              data-testid={`template-card-${tmpl.slug}`}
              className="bg-white rounded-xl border border-slate-200 shadow-sm hover:shadow-md hover:border-slate-300 transition-all overflow-hidden flex flex-col justify-between"
            >
              <div>
                {/* Thumbnail Header */}
                <div className="h-44 bg-slate-100 relative overflow-hidden border-b border-slate-200 flex items-center justify-center">
                  <img
                    src={tmpl.thumbnail_url || `/api/v1/clubs/${clubId}/documents/templates/${tmpl.id}/thumbnail`}
                    alt={tmpl.name}
                    className="w-full h-full object-cover object-top hover:scale-105 transition-transform duration-300"
                    onError={(e) => {
                      const target = e.target as HTMLElement;
                      target.style.display = 'none';
                    }}
                  />
                  <div className="absolute top-2.5 left-2.5 flex items-center gap-1.5 flex-wrap">
                    {tmpl.is_system ? (
                      <span className="text-[10px] font-bold uppercase tracking-wider bg-blue-100 text-blue-900 px-2 py-0.5 rounded-full border border-blue-300 flex items-center gap-1">
                        <Shield className="w-3 h-3 text-blue-700" />
                        System Template
                      </span>
                    ) : (
                      <span className="text-[10px] font-bold uppercase tracking-wider bg-amber-100 text-amber-900 px-2 py-0.5 rounded-full border border-amber-300 flex items-center gap-1">
                        <Sparkles className="w-3 h-3 text-amber-700" />
                        Club Custom ({tmpl.status})
                      </span>
                    )}
                    {tmpl.numbering_series && (
                      <span className="text-[10px] font-mono font-bold bg-slate-900/80 text-white px-2 py-0.5 rounded-full backdrop-blur-xs flex items-center gap-1">
                        <Hash className="w-2.5 h-2.5 text-amber-400" />
                        {tmpl.numbering_series}
                      </span>
                    )}
                  </div>

                  <div className="absolute top-2.5 right-2.5">
                    <span className="text-[10px] font-semibold bg-white/90 text-slate-700 px-2 py-0.5 rounded-full border border-slate-200 backdrop-blur-xs">
                      {tmpl.stage ? tmpl.stage.replace('_', ' ') : 'General'}
                    </span>
                  </div>
                </div>

                {/* Template Body */}
                <div className="p-5 space-y-2.5">
                  <div className="flex items-start justify-between gap-2">
                    <h3 className="text-base font-bold text-slate-900 leading-snug">{tmpl.name}</h3>
                  </div>

                  <p className="text-xs text-slate-600 line-clamp-2 leading-relaxed">
                    {tmpl.description || 'Institutional document template compliant with SVNIT Surat standards.'}
                  </p>

                  <div className="pt-2 flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
                    <span className="inline-flex items-center gap-1 bg-slate-50 border border-slate-200 px-2 py-0.5 rounded">
                      <Tag className="w-3 h-3 text-slate-400" />
                      {tmpl.category || 'Official Document'}
                    </span>
                    {tmpl.is_system && (
                      <span className="text-[11px] text-slate-400 italic">
                        Read-only
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="p-4 bg-slate-50/70 border-t border-slate-100 flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => onSelectTemplate(tmpl.slug || tmpl.id)}
                  className="flex-1 inline-flex items-center justify-center gap-1.5 bg-[#1b365d] hover:bg-[#152a48] text-white px-3 py-2 rounded-lg text-xs font-bold transition-colors shadow-xs"
                >
                  <PlusCircle className="w-3.5 h-3.5" />
                  Use Template
                </button>

                {tmpl.is_system && canManage && (
                  <button
                    type="button"
                    data-testid={`fork-btn-${tmpl.slug}`}
                    onClick={() => setActionModal({ type: 'fork', tmpl, value: `${tmpl.name} (Custom)` })}
                    title="Fork into this club to customize schema and layout"
                    className="inline-flex items-center gap-1.5 bg-white hover:bg-slate-100 text-slate-700 border border-slate-300 px-3 py-2 rounded-lg text-xs font-semibold transition-colors"
                  >
                    <Copy className="w-3.5 h-3.5 text-amber-600" />
                    <span>Customize</span>
                  </button>
                )}

                {!tmpl.is_system && canManage && (
                  <div className="flex items-center gap-1.5">
                    {onOpenEditor && (
                      <button
                        type="button"
                        data-testid={`edit-draft-btn-${tmpl.id}`}
                        onClick={() => onOpenEditor(tmpl.id)}
                        title="Open template in editor"
                        className="inline-flex items-center gap-1.5 bg-blue-50 hover:bg-blue-100 text-blue-700 border border-blue-200 px-3 py-2 rounded-lg text-xs font-semibold transition-colors"
                      >
                        <FileText className="w-3.5 h-3.5" />
                        <span>Edit Draft</span>
                      </button>
                    )}
                    <button
                      type="button"
                      data-testid={`rename-btn-${tmpl.id}`}
                      onClick={() => setActionModal({ type: 'rename', tmpl, value: tmpl.name })}
                      title="Rename this custom draft"
                      className="p-2 text-slate-600 hover:text-slate-900 bg-white hover:bg-slate-100 border border-slate-200 rounded-lg transition-colors"
                    >
                      <Edit2 className="w-3.5 h-3.5" />
                    </button>
                    <button
                      type="button"
                      data-testid={`archive-btn-${tmpl.id}`}
                      onClick={() => setActionModal({ type: 'archive', tmpl })}
                      title="Archive / Delete this custom draft"
                      className="p-2 text-red-600 hover:text-red-700 bg-white hover:bg-red-50 border border-slate-200 rounded-lg transition-colors"
                    >
                      <Archive className="w-3.5 h-3.5" />
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Unified Action Modal */}
      {actionModal && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl border border-slate-200 max-w-md w-full p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                {actionModal.type === 'fork' && <><Copy className="w-4 h-4 text-amber-600" /> Customize Template (Fork)</>}
                {actionModal.type === 'rename' && <><Edit2 className="w-4 h-4 text-[#1b365d]" /> Rename Custom Draft</>}
                {actionModal.type === 'archive' && <><Archive className="w-4 h-4 text-red-600" /> Archive Custom Draft</>}
                {actionModal.type === 'blank' && <><PlusCircle className="w-4 h-4 text-blue-600" /> New Blank Template</>}
              </h3>
              <button
                type="button"
                onClick={() => setActionModal(null)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            {actionModal.type === 'fork' && (
              <p className="text-xs text-slate-600 leading-relaxed">
                This creates an independent draft copy of <strong className="text-slate-900">{actionModal.tmpl?.name}</strong> for your club.
              </p>
            )}
            {actionModal.type === 'archive' && (
              <p className="text-xs text-slate-600 leading-relaxed">
                Are you sure you want to archive <strong className="text-slate-900">{actionModal.tmpl?.name}</strong>? It will be removed from your active gallery.
              </p>
            )}
            <form onSubmit={handleModalSubmit} className="space-y-4">
              {actionModal.type !== 'archive' && (
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">
                    {actionModal.type === 'blank' ? 'Template Name *' : actionModal.type === 'fork' ? 'Draft Template Name' : 'New Template Name'}
                  </label>
                  <input
                    type="text"
                    required
                    value={actionModal.value || ''}
                    onChange={(e) => setActionModal({ ...actionModal, value: e.target.value })}
                    placeholder={actionModal.type === 'blank' ? 'e.g. Sponsorship Request Letter' : undefined}
                    className="w-full text-xs p-2.5 rounded-lg border border-slate-300 focus:ring-2 focus:ring-[#1b365d]"
                  />
                </div>
              )}
              {modalError && (
                <div className="p-2.5 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700 flex items-center gap-1.5">
                  <AlertCircle className="w-4 h-4 flex-shrink-0 text-red-500" />
                  <span>{modalError}</span>
                </div>
              )}
              <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setActionModal(null)}
                  className="px-4 py-2 text-xs font-semibold text-slate-600 hover:text-slate-800"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={modalSubmitting || (actionModal.type === 'blank' && !actionModal.value?.trim())}
                  className={`px-5 py-2 rounded-lg text-xs font-bold transition-colors disabled:opacity-50 inline-flex items-center gap-1.5 text-white ${
                    actionModal.type === 'archive'
                      ? 'bg-red-600 hover:bg-red-700'
                      : 'bg-[#1b365d] hover:bg-[#152a48]'
                  }`}
                >
                  {modalSubmitting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  {actionModal.type === 'fork' ? 'Create Club Fork' : actionModal.type === 'archive' ? 'Archive Draft' : actionModal.type === 'rename' ? 'Save Name' : 'Create & Open Editor'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Ambiguous Logo Selection Modal */}
      {ambiguousLogoModal && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6 border border-slate-200">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100 mb-4">
              <h3 className="font-bold text-sm text-slate-800 flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-blue-600" />
                Select Club Logo
              </h3>
              <button
                onClick={() => {
                  const tmplId = ambiguousLogoModal.templateId;
                  setAmbiguousLogoModal(null);
                  if (onOpenEditor) onOpenEditor(tmplId);
                }}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <p className="text-xs text-slate-600 mb-4">
              Multiple matching logos were found in your club&apos;s asset library. Choose which logo to display in this template&apos;s letterhead:
            </p>
            <div className="space-y-2 mb-4">
              {ambiguousLogoModal.candidates.map((c: any) => (
                <button
                  key={c.asset_id}
                  onClick={() => handlePickLogo(c.asset_id)}
                  className="w-full flex items-center justify-between p-2.5 rounded-lg border border-slate-200 hover:border-blue-500 hover:bg-blue-50 transition-all text-left"
                >
                  <div className="flex items-center gap-3">
                    <img
                      src={c.url}
                      alt={c.filename}
                      className="w-8 h-8 object-contain rounded bg-white p-0.5 border border-slate-200"
                    />
                    <span className="text-xs font-semibold text-slate-700">{c.filename}</span>
                  </div>
                  <span className="text-xs text-blue-600 font-bold">Use this →</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Template Wizard Modal */}
      <TemplateWizardModal
        clubId={clubId}
        isOpen={showWizardModal}
        onClose={() => setShowWizardModal(false)}
        onSuccess={(id) => {
          fetchTemplates();
          if (onOpenEditor) onOpenEditor(id);
        }}
      />

      {/* Template Import Modal */}
      <TemplateImportModal
        clubId={clubId}
        isOpen={showImportModal}
        onClose={() => setShowImportModal(false)}
        onSuccess={(id) => {
          fetchTemplates();
          if (onOpenEditor) onOpenEditor(id);
        }}
      />
    </div>
  );
};
