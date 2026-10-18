import React, { useState, useEffect, useRef } from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import TextAlign from '@tiptap/extension-text-align';
import {
  ArrowLeft, Save, Eye, CheckCircle2, AlertCircle, RefreshCw,
  Bold as BoldIcon, Italic as ItalicIcon, Underline as UnderlineIcon,
  AlignLeft, AlignCenter, AlignRight, AlignJustify, List, ListOrdered,
  Plus, Trash2, SplitSquareVertical,
  Table as TableIcon, Layers, FileText, Check, Lock, X, Sparkles
} from 'lucide-react';
import { api } from '../../api/client';
import { AiSuggestedBlock, FieldChip, InfoTable, RepeatingTable, SignatureGrid, PageBreak } from './extensions';

interface TemplateField {
  key: string;
  label: string;
  type: string;
  required: boolean;
  ask?: string;
  defer_ok?: boolean;
  sensitive?: boolean;
  values?: string[];
  computed?: any;
  format?: string;
  ai_suggested?: boolean;
}

interface TemplateEditorProps {
  clubId: string;
  templateId: string;
  onBack: () => void;
}

export const TemplateEditor: React.FC<TemplateEditorProps> = ({ clubId, templateId, onBack }) => {
  const [template, setTemplate] = useState<any>(null);
  const [fields, setFields] = useState<TemplateField[]>([]);
  const [letterheads, setLetterheads] = useState<any[]>([]);
  const [selectedLetterheadId, setSelectedLetterheadId] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<'saved' | 'saving' | 'unsaved'>('saved');
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewPages, setPreviewPages] = useState<string[]>([]);
  const [showPreviewModal, setShowPreviewModal] = useState(false);
  const [validationReport, setValidationReport] = useState<any>(null);
  const [showValidationModal, setShowValidationModal] = useState(false);
  const [newFieldName, setNewFieldName] = useState('');
  const [newFieldType, setNewFieldType] = useState('text');
  const [newFieldRequired, setNewFieldRequired] = useState(true);
  const [showAddFieldModal, setShowAddFieldModal] = useState(false);
  const [editingFieldKey, setEditingFieldKey] = useState<string | null>(null);
  const [renamedKeyVal, setRenamedKeyVal] = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false);

  // AI Review Gate State
  const [unreviewedModal, setUnreviewedModal] = useState<any[] | null>(null);
  const [showReviewAllConfirm, setShowReviewAllConfirm] = useState(false);
  const [reviewingAi, setReviewingAi] = useState(false);

  // Logo search by text
  const [logoSearchText, setLogoSearchText] = useState('');
  const [searchingLogo, setSearchingLogo] = useState(false);
  const [logoSearchMsg, setLogoSearchMsg] = useState<string | null>(null);

  const handleResolveLogoText = async () => {
    if (!logoSearchText.trim()) return;
    try {
      setSearchingLogo(true);
      setLogoSearchMsg(null);
      const res = await api.documents.resolveLogo(clubId, logoSearchText.trim());
      if (res.status === 'resolved') {
        setLogoSearchMsg(`Resolved to: ${res.filename}`);
        // If there is a letterhead matching this logo or default
        const matchingLh = letterheads.find(lh => lh.club_logo_url?.includes(res.asset_id || '') || lh.club_logo_url?.includes(res.filename || ''));
        if (matchingLh) {
          setSelectedLetterheadId(matchingLh.id);
        }
        setSaveStatus('unsaved');
        triggerAutosave();
      } else if (res.status === 'ambiguous') {
        const count = res.candidates?.length || 0;
        setLogoSearchMsg(`Found ${count} matching logos. Please pick from the letterhead dropdown.`);
      } else {
        setLogoSearchMsg('No matching logo found in club asset library.');
      }
    } catch (err: any) {
      setLogoSearchMsg(err.message || 'Error resolving logo.');
    } finally {
      setSearchingLogo(false);
    }
  };

  const autosaveTimerRef = useRef<any>(null);

  // TipTap Editor initialization
  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: { levels: [1, 2, 3] },
      }),
      TextAlign.configure({
        types: ['heading', 'paragraph'],
      }),
      AiSuggestedBlock,
      FieldChip,
      InfoTable,
      RepeatingTable,
      SignatureGrid,
      PageBreak,
    ],
    content: { type: 'doc', content: [] },
    onUpdate: ({ editor: currentEditor, transaction }: any) => {
      setSaveStatus('unsaved');
      triggerAutosave();

      if (transaction && transaction.docChanged) {
        const { from } = currentEditor.state.selection;
        const resolved = currentEditor.state.doc.resolve(from);
        for (let d = resolved.depth; d > 0; d--) {
          const node = resolved.node(d);
          if (node.attrs && (node.attrs.ai_suggested || node.attrs.official_wording_required)) {
            const pos = resolved.before(d);
            currentEditor.commands.command(({ tr }: any) => {
              tr.setNodeMarkup(pos, undefined, {
                ...node.attrs,
                ai_suggested: false,
                official_wording_required: false,
              });
              return true;
            });
            break;
          }
        }
      }
    },
  });

  // Load draft data & letterheads
  useEffect(() => {
    let isMounted = true;
    const fetchDraft = async () => {
      setLoading(true);
      try {
        const [draftData, lhList] = await Promise.all([
          api.documents.getTemplateDraft(clubId, templateId),
          api.documents.listLetterheads(clubId).catch(() => []),
        ]);

        if (!isMounted) return;
        setTemplate(draftData);
        setFields(draftData.fields || []);
        setLetterheads(lhList || []);
        const defaultLhId = draftData.letterhead_id || (lhList && lhList.length > 0 ? lhList[0].id : '');
        setSelectedLetterheadId(defaultLhId);
        setValidationReport(draftData.validation_report || null);

        if (editor && draftData.editor_json) {
          editor.commands.setContent(draftData.editor_json);
        }
      } catch (err: any) {
        console.error('Failed to load template draft:', err);
        alert(err.message || 'Failed to load template draft');
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    fetchDraft();
    return () => {
      isMounted = false;
      if (autosaveTimerRef.current) clearTimeout(autosaveTimerRef.current);
    };
  }, [clubId, templateId, editor]);

  // Sync editor content if template loaded before editor was ready
  useEffect(() => {
    if (editor && template?.editor_json && editor.isEmpty) {
      editor.commands.setContent(template.editor_json);
    }
  }, [editor, template]);

  // Debounced Autosave (1.5s)
  const triggerAutosave = () => {
    if (autosaveTimerRef.current) clearTimeout(autosaveTimerRef.current);
    autosaveTimerRef.current = setTimeout(() => {
      handleSave(false);
    }, 1500);
  };

  const handleSave = async (showToast = true) => {
    if (!editor || !template) return;
    setSaving(true);
    setSaveStatus('saving');
    try {
      const editorJson = editor.getJSON();
      const updated = await api.documents.saveTemplateDraft(clubId, templateId, {
        name: template.name,
        category: template.category,
        description: template.description,
        editor_json: editorJson,
        fields: fields,
        letterhead_id: selectedLetterheadId || null,
      });
      setTemplate(updated);
      setSaveStatus('saved');
    } catch (err: any) {
      console.error('Save failed:', err);
      setSaveStatus('unsaved');
      if (showToast) alert(err.message || 'Failed to save draft');
    } finally {
      setSaving(false);
    }
  };

  // Compile and Validate
  const handleCompile = async () => {
    if (!editor || !template) return;
    setSaving(true);
    try {
      const editorJson = editor.getJSON();
      const report = await api.documents.compileTemplate(clubId, templateId, {
        name: template.name,
        category: template.category,
        description: template.description,
        editor_json: editorJson,
        fields: fields,
        letterhead_id: selectedLetterheadId || null,
      });
      setValidationReport(report);
      setShowValidationModal(true);
      setSaveStatus('saved');
    } catch (err: any) {
      alert(err.message || 'Compilation failed');
    } finally {
      setSaving(false);
    }
  };

  // Live Preview with synthetic dummy data
  const handlePreview = async () => {
    if (!editor || !template) return;
    setPreviewLoading(true);
    setShowPreviewModal(true);
    try {
      const editorJson = editor.getJSON();
      const res = await api.documents.previewTemplate(clubId, templateId, {
        name: template.name,
        category: template.category,
        description: template.description,
        editor_json: editorJson,
        fields: fields,
        letterhead_id: selectedLetterheadId || null,
      });
      setPreviewPages(res.pages || []);
    } catch (err: any) {
      alert(err.message || 'Preview generation failed');
      setShowPreviewModal(false);
    } finally {
      setPreviewLoading(false);
    }
  };

  // AI Content Review Handlers
  const handleReviewItem = async (fieldKey?: string, blockIndex?: number) => {
    try {
      setReviewingAi(true);
      await api.documents.reviewAiTemplate(clubId, templateId, {
        field_keys: fieldKey ? [fieldKey] : undefined,
        block_indices: blockIndex !== undefined ? [blockIndex] : undefined,
      });
      if (fieldKey) {
        setFields(prev => prev.map(f => f.key === fieldKey ? { ...f, ai_suggested: false } : f));
      }
      setSaveStatus('unsaved');
      triggerAutosave();
    } catch (err: any) {
      alert(err.message || 'Failed to mark item reviewed');
    } finally {
      setReviewingAi(false);
    }
  };

  const handleReviewAll = async () => {
    try {
      setReviewingAi(true);
      await api.documents.reviewAiTemplate(clubId, templateId, { all: true });
      setFields(prev => prev.map(f => ({ ...f, ai_suggested: false })));
      if (editor) {
        const { tr } = editor.state;
        editor.state.doc.descendants((node, pos) => {
          if (node.attrs && (node.attrs.ai_suggested || node.attrs.official_wording_required)) {
            tr.setNodeMarkup(pos, undefined, {
              ...node.attrs,
              ai_suggested: false,
              official_wording_required: false,
            });
          }
        });
        editor.view.dispatch(tr);
      }
      setShowReviewAllConfirm(false);
      setUnreviewedModal(null);
      setSaveStatus('unsaved');
      triggerAutosave();
    } catch (err: any) {
      alert(err.message || 'Failed to review all items');
    } finally {
      setReviewingAi(false);
    }
  };

  // Publish Template
  const handlePublish = async () => {
    if (!editor || !template) return;
    if (!confirm(`Are you sure you want to publish "${template.name}"? Published templates create an immutable version for all documents.`)) {
      return;
    }
    setSaving(true);
    try {
      await handleSave(false);
      const res = await api.documents.publishTemplate(clubId, templateId);
      setTemplate((prev: any) => ({ ...prev, status: 'published' }));
      alert(`Template "${res.name}" successfully published as Version ${res.id ? 'Active' : ''}!`);
    } catch (err: any) {
      if (err.status === 409 && err.detail?.unreviewed_items) {
        setUnreviewedModal(err.detail.unreviewed_items);
      } else {
        alert(err.message || 'Publishing failed');
      }
    } finally {
      setSaving(false);
    }
  };

  // Insert field chip at cursor position
  const insertFieldChip = (fieldKey: string, fieldLabel: string, fieldType = 'text') => {
    if (!editor) return;
    editor.chain().focus().insertContent({
      type: 'fieldChip',
      attrs: {
        fieldName: fieldKey,
        label: fieldLabel || fieldKey,
        fieldType: fieldType,
      },
    }).run();
  };

  // Add new field and insert chip
  const handleAddField = (e: React.FormEvent) => {
    e.preventDefault();
    const cleanKey = newFieldName.trim().toLowerCase().replace(/[^a-z0-9_]/g, '_');
    if (!cleanKey) return;

    if (fields.some(f => f.key === cleanKey)) {
      alert(`Field "${cleanKey}" already exists.`);
      return;
    }

    const newF: TemplateField = {
      key: cleanKey,
      label: newFieldName.trim(),
      type: newFieldType,
      required: newFieldRequired,
      ask: `Enter ${newFieldName.trim()}`,
      defer_ok: false,
      sensitive: false,
    };

    const nextFields = [...fields, newF];
    setFields(nextFields);
    insertFieldChip(cleanKey, newF.label, newF.type);
    setNewFieldName('');
    setShowAddFieldModal(false);
    triggerAutosave();
  };

  // Rename a field and update every chip across the TipTap document
  const handleRenameField = (oldKey: string) => {
    const cleanNewKey = renamedKeyVal.trim().toLowerCase().replace(/[^a-z0-9_]/g, '_');
    if (!cleanNewKey || cleanNewKey === oldKey) {
      setEditingFieldKey(null);
      return;
    }

    if (fields.some(f => f.key === cleanNewKey)) {
      alert(`Field key "${cleanNewKey}" is already used.`);
      return;
    }

    // 1. Update fields state
    const nextFields = fields.map(f => {
      if (f.key === oldKey) {
        return { ...f, key: cleanNewKey, label: f.label === oldKey ? cleanNewKey : f.label, ai_suggested: false };
      }
      return f;
    });
    setFields(nextFields);

    // 2. Traverse and update TipTap document
    if (editor) {
      const { tr } = editor.state;
      let docChanged = false;

      editor.state.doc.descendants((node, pos) => {
        if (node.type.name === 'fieldChip' && node.attrs.fieldName === oldKey) {
          tr.setNodeMarkup(pos, undefined, {
            ...node.attrs,
            fieldName: cleanNewKey,
            label: node.attrs.label === oldKey ? cleanNewKey : node.attrs.label,
          });
          docChanged = true;
        } else if (node.type.name === 'infoTable') {
          const rows = node.attrs.rows || [];
          let rowUpdated = false;
          const nextRows = rows.map((r: any) => {
            if (r.field === oldKey) {
              rowUpdated = true;
              return { ...r, field: cleanNewKey };
            }
            return r;
          });
          if (rowUpdated) {
            tr.setNodeMarkup(pos, undefined, { ...node.attrs, rows: nextRows });
            docChanged = true;
          }
        } else if (node.type.name === 'repeatingTable') {
          if (node.attrs.listVariable === oldKey) {
            tr.setNodeMarkup(pos, undefined, { ...node.attrs, listVariable: cleanNewKey });
            docChanged = true;
          }
        }
      });

      if (docChanged) {
        editor.view.dispatch(tr);
      }
    }

    setEditingFieldKey(null);
    setRenamedKeyVal('');
    triggerAutosave();
  };

  const removeField = (fieldKey: string) => {
    if (!confirm(`Remove field "${fieldKey}"? Existing chips will remain in the document.`)) return;
    setFields(fields.filter(f => f.key !== fieldKey));
    triggerAutosave();
  };

  // Block inserters
  const insertInfoTable = () => {
    if (!editor) return;
    editor.chain().focus().insertContent({
      type: 'infoTable',
      attrs: {
        title: 'Event Overview',
        rows: [
          { label: 'Event Name', field: 'event_name', value: '' },
          { label: 'Date', field: 'event_date', value: '' },
          { label: 'Venue', field: 'venue', value: '' },
        ],
      },
    }).run();
  };

  const insertRepeatingTable = () => {
    if (!editor) return;
    editor.chain().focus().insertContent({
      type: 'repeatingTable',
      attrs: {
        listVariable: 'sponsorship_tiers',
        itemAlias: 'tier',
        columns: [
          { key: 'tier_name', label: 'Tier', align: 'left' },
          { key: 'benefits', label: 'Deliverables & Benefits', align: 'left' },
          { key: 'amount', label: 'Contribution (INR)', align: 'right' },
        ],
        hasTotal: true,
        totalLabel: 'Total Expected Contribution',
        totalField: 'amount',
        totalVarName: 'total_sponsorship_amount',
      },
    }).run();

    // Ensure listVariable and total fields exist in fields list
    if (!fields.some(f => f.key === 'sponsorship_tiers')) {
      setFields(prev => [
        ...prev,
        { key: 'sponsorship_tiers', label: 'Sponsorship Tiers', type: 'table', required: true, ask: 'Tiers and contribution amounts' },
      ]);
    }
  };

  const insertSignatureGrid = () => {
    if (!editor) return;
    editor.chain().focus().insertContent({
      type: 'signatureGrid',
      attrs: {
        columns: 3,
        signatures: [
          { label: 'Student Coordinator', designation: 'ACM Student Chapter' },
          { label: 'Faculty Advisor', designation: 'DoCSE, SVNIT' },
          { label: 'Head of Department', designation: 'DoCSE, SVNIT' },
        ],
      },
    }).run();
  };

  const insertPageBreak = () => {
    if (!editor) return;
    editor.chain().focus().insertContent({
      type: 'pageBreak',
    }).run();
  };

  if (loading || !template) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-3">
        <RefreshCw className="w-8 h-8 text-blue-600 animate-spin" />
        <p className="text-sm font-medium text-slate-600">Loading Template Editor...</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col min-h-screen bg-slate-100 -m-6">
      {/* Top Navbar */}
      <header className="sticky top-0 z-30 bg-white border-b border-slate-200 px-6 py-3 shadow-sm flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button
            onClick={onBack}
            className="p-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 text-slate-600 transition-colors"
            title="Back to Template Gallery"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>

          <div>
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={template.name}
                onChange={e => {
                  setTemplate({ ...template, name: e.target.value });
                  setSaveStatus('unsaved');
                  triggerAutosave();
                }}
                className="text-base font-bold text-slate-900 border-b border-transparent hover:border-slate-300 focus:border-blue-600 focus:outline-none bg-transparent px-1 py-0.5"
                placeholder="Template Name"
              />
              <span className={`px-2 py-0.5 rounded text-[11px] font-semibold uppercase tracking-wider ${
                template.status === 'published' ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'
              }`}>
                {template.status} (v{template.version_no || 1})
              </span>
            </div>
            <div className="flex items-center gap-2 text-xs text-slate-500 pl-1 mt-0.5">
              <span>{template.category || 'General'}</span>
              <span>•</span>
              <span className="flex items-center gap-1">
                {saveStatus === 'saved' && <><Check className="w-3 h-3 text-emerald-600" /> Saved</>}
                {saveStatus === 'saving' && <><RefreshCw className="w-3 h-3 text-blue-600 animate-spin" /> Saving...</>}
                {saveStatus === 'unsaved' && <><span className="w-2 h-2 rounded-full bg-amber-500 inline-block" /> Unsaved changes</>}
              </span>
            </div>
          </div>
        </div>

        {/* Header Actions */}
        <div className="flex items-center gap-3">
          {/* Letterhead Picker */}
          <div className="flex items-center gap-1.5 bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1 text-xs">
            <span title="SVNIT Emblem Locked"><Lock className="w-3.5 h-3.5 text-blue-700" /></span>
            <span className="font-semibold text-slate-700">SVNIT Emblem</span>
            <span className="text-slate-300">|</span>
            <select
              value={selectedLetterheadId || (letterheads[0]?.id ?? '')}
              onChange={e => {
                setSelectedLetterheadId(e.target.value);
                setSaveStatus('unsaved');
                triggerAutosave();
              }}
              className="bg-transparent text-slate-700 focus:outline-none font-medium cursor-pointer"
            >
              {letterheads.map(lh => (
                <option key={lh.id} value={lh.id}>{lh.name}</option>
              ))}
            </select>
          </div>

          {/* Live Preview Button */}
          <button
            onClick={handlePreview}
            disabled={previewLoading}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-semibold border border-slate-300 transition-colors"
          >
            {previewLoading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Eye className="w-3.5 h-3.5 text-blue-600" />}
            Live Preview
          </button>

          {/* Compile & Validate */}
          <button
            onClick={handleCompile}
            disabled={saving}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-50 hover:bg-blue-100 text-blue-700 rounded-lg text-xs font-semibold border border-blue-200 transition-colors"
          >
            <CheckCircle2 className="w-3.5 h-3.5 text-blue-600" />
            Compile & Validate
          </button>

          {/* Publish Button */}
          <button
            onClick={handlePublish}
            disabled={saving}
            className="flex items-center gap-1.5 px-4 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold shadow-sm transition-colors"
          >
            <Save className="w-3.5 h-3.5" />
            Publish Template
          </button>
        </div>
      </header>

      {/* Main Split Layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Editor Area (Left 70%) */}
        <div className="flex-1 flex flex-col overflow-y-auto p-6 items-center">
          {/* Formatting Toolbar */}
          {editor && (
            <div className="sticky top-2 z-20 w-full max-w-4xl bg-white/95 backdrop-blur border border-slate-200 rounded-xl p-2.5 mb-4 shadow-sm flex flex-col gap-2 text-slate-700">
              {/* Primary Toolbar Row */}
              <div className="flex flex-wrap items-center gap-1.5 w-full">
                {/* Simplified Headings */}
                <select
                  onChange={e => {
                    const val = e.target.value;
                    if (val === 'p') editor.chain().focus().setParagraph().run();
                    else if (val === 'h1') editor.chain().focus().toggleHeading({ level: 1 }).run();
                    else if (val === 'h2') editor.chain().focus().toggleHeading({ level: 2 }).run();
                    else if (val === 'h3') editor.chain().focus().toggleHeading({ level: 3 }).run();
                  }}
                  className="text-xs font-medium border border-slate-200 rounded px-2 py-1 bg-white focus:outline-none mr-1"
                  value={
                    editor.isActive('heading', { level: 1 }) ? 'h1' :
                    editor.isActive('heading', { level: 2 }) ? 'h2' :
                    editor.isActive('heading', { level: 3 }) ? 'h3' : 'p'
                  }
                >
                  <option value="p">Normal text</option>
                  <option value="h1">Title</option>
                  <option value="h2">Heading</option>
                  <option value="h3">Subheading</option>
                </select>

                <div className="w-px h-5 bg-slate-200 mx-1" />

                {/* Bold, Italic, Underline */}
                <button
                  onClick={() => editor.chain().focus().toggleBold().run()}
                  className={`p-1.5 rounded hover:bg-slate-100 ${editor.isActive('bold') ? 'bg-slate-200 text-blue-700 font-bold' : ''}`}
                  title="Bold (Ctrl+B)"
                >
                  <BoldIcon className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={() => editor.chain().focus().toggleItalic().run()}
                  className={`p-1.5 rounded hover:bg-slate-100 ${editor.isActive('italic') ? 'bg-slate-200 text-blue-700' : ''}`}
                  title="Italic (Ctrl+I)"
                >
                  <ItalicIcon className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={() => editor.chain().focus().toggleUnderline().run()}
                  className={`p-1.5 rounded hover:bg-slate-100 ${editor.isActive('underline') ? 'bg-slate-200 text-blue-700' : ''}`}
                  title="Underline (Ctrl+U)"
                >
                  <UnderlineIcon className="w-3.5 h-3.5" />
                </button>

                <div className="w-px h-5 bg-slate-200 mx-1" />

                {/* Align Left & Center */}
                <button
                  onClick={() => editor.chain().focus().setTextAlign('left').run()}
                  className={`p-1.5 rounded hover:bg-slate-100 ${editor.isActive({ textAlign: 'left' }) ? 'bg-slate-200 text-blue-700' : ''}`}
                  title="Align Left"
                >
                  <AlignLeft className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={() => editor.chain().focus().setTextAlign('center').run()}
                  className={`p-1.5 rounded hover:bg-slate-100 ${editor.isActive({ textAlign: 'center' }) ? 'bg-slate-200 text-blue-700' : ''}`}
                  title="Align Center"
                >
                  <AlignCenter className="w-3.5 h-3.5" />
                </button>

                <div className="w-px h-5 bg-slate-200 mx-1" />

                {/* Lists */}
                <button
                  onClick={() => editor.chain().focus().toggleBulletList().run()}
                  className={`p-1.5 rounded hover:bg-slate-100 ${editor.isActive('bulletList') ? 'bg-slate-200 text-blue-700' : ''}`}
                  title="Bullet List"
                >
                  <List className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={() => editor.chain().focus().toggleOrderedList().run()}
                  className={`p-1.5 rounded hover:bg-slate-100 ${editor.isActive('orderedList') ? 'bg-slate-200 text-blue-700' : ''}`}
                  title="Numbered List"
                >
                  <ListOrdered className="w-3.5 h-3.5" />
                </button>

                <div className="w-px h-5 bg-slate-200 mx-1" />

                {/* Insert Field button */}
                <button
                  onClick={() => setShowAddFieldModal(true)}
                  className="flex items-center gap-1 px-2.5 py-1 rounded bg-indigo-50 hover:bg-indigo-100 text-[11px] font-semibold text-indigo-700 border border-indigo-200 shadow-2xs"
                  title="Add new template field"
                >
                  <Plus className="w-3 h-3 text-indigo-600" />
                  + Field
                </button>

                {/* Advanced Toggle Button */}
                <button
                  type="button"
                  data-testid="advanced-toolbar-toggle"
                  onClick={() => setShowAdvanced(!showAdvanced)}
                  className={`flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold border transition-colors ml-auto ${
                    showAdvanced ? 'bg-blue-50 border-blue-300 text-blue-700' : 'bg-slate-100 border-slate-200 hover:bg-slate-200 text-slate-700'
                  }`}
                >
                  <span>Advanced</span>
                  <span className="text-[10px]">{showAdvanced ? '▲' : '▼'}</span>
                </button>
              </div>

              {/* Advanced Options Strip (Hidden behind "Advanced") */}
              {showAdvanced && (
                <div data-testid="advanced-toolbar-panel" className="w-full pt-2 border-t border-slate-200 flex flex-wrap items-center gap-2 text-xs">
                  <div className="flex items-center gap-1">
                    <span className="text-[11px] font-medium text-slate-500 mr-1">Align:</span>
                    <button
                      onClick={() => editor.chain().focus().setTextAlign('right').run()}
                      className={`p-1.5 rounded hover:bg-slate-100 ${editor.isActive({ textAlign: 'right' }) ? 'bg-slate-200 text-blue-700' : ''}`}
                      title="Align Right"
                    >
                      <AlignRight className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => editor.chain().focus().setTextAlign('justify').run()}
                      className={`p-1.5 rounded hover:bg-slate-100 ${editor.isActive({ textAlign: 'justify' }) ? 'bg-slate-200 text-blue-700' : ''}`}
                      title="Justify"
                    >
                      <AlignJustify className="w-3.5 h-3.5" />
                    </button>
                  </div>

                  <div className="w-px h-5 bg-slate-200 mx-1" />

                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="text-[11px] font-medium text-slate-500 mr-1">Insert Blocks:</span>
                    <button
                      onClick={insertInfoTable}
                      className="flex items-center gap-1 px-2 py-1 rounded bg-slate-100 hover:bg-slate-200 text-[11px] font-semibold text-slate-700"
                      title="Insert 2-column Info Table"
                    >
                      <TableIcon className="w-3 h-3 text-slate-600" />
                      + Info Table
                    </button>

                    <button
                      onClick={insertRepeatingTable}
                      className="flex items-center gap-1 px-2 py-1 rounded bg-blue-50 hover:bg-blue-100 text-[11px] font-semibold text-blue-700 border border-blue-200"
                      title="Insert Repeating Table with Computed Total"
                    >
                      <Layers className="w-3 h-3 text-blue-600" />
                      + Repeating Table
                    </button>

                    <button
                      onClick={insertSignatureGrid}
                      className="flex items-center gap-1 px-2 py-1 rounded bg-slate-100 hover:bg-slate-200 text-[11px] font-semibold text-slate-700"
                      title="Insert Signature Grid (keeps rows together)"
                    >
                      <SplitSquareVertical className="w-3 h-3 text-slate-600" />
                      + Signature Grid
                    </button>

                    <button
                      onClick={insertPageBreak}
                      className="flex items-center gap-1 px-2 py-1 rounded bg-slate-100 hover:bg-slate-200 text-[11px] font-semibold text-slate-700"
                      title="Insert Page Break"
                    >
                      <FileText className="w-3 h-3 text-slate-600" />
                      + Page Break
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Document Sheet (A4 Canvas) */}
          <div className="w-full max-w-4xl bg-white border border-slate-300 rounded-lg shadow-md p-10 min-h-[900px] mb-12">
            {/* AI-Suggested Draft Banner */}
            {(fields.some((f: any) => f.ai_suggested) || (template?.editor_json?.content || []).some((b: any) => b.ai_suggested)) && (
              <div data-testid="ai-suggested-banner" className="mb-6 p-4 rounded-xl bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 text-xs text-blue-900 flex items-center justify-between gap-3 shadow-xs">
                <div className="flex items-start gap-2.5">
                  <Sparkles className="w-4 h-4 text-blue-600 flex-shrink-0 mt-0.5" />
                  <div>
                    <div className="font-bold text-blue-950 flex items-center gap-2">
                      <span>AI-Suggested Template Draft</span>
                      <span className="text-[10px] bg-blue-200 text-blue-800 font-bold px-1.5 py-0.2 rounded-full">DRAFT</span>
                    </div>
                    <p className="text-blue-700 mt-0.5">
                      This template was drafted from plain text. Review the suggested fields, layout blocks, and signees below. All AI-suggested content must be reviewed before publishing.
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  data-testid="review-all-ai-btn"
                  onClick={() => setShowReviewAllConfirm(true)}
                  disabled={reviewingAi}
                  className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-bold shadow-xs transition-colors flex items-center gap-1.5 flex-shrink-0"
                >
                  <Check className="w-3.5 h-3.5" />
                  Review All
                </button>
              </div>
            )}

            {/* Visual Document Header Preview & Letterhead Picker */}
            {(() => {
              const currentLetterhead = letterheads.find(lh => lh.id === selectedLetterheadId) || letterheads[0];
              return (
                <div className="pb-4 mb-6 border-b border-slate-200 flex items-center justify-between gap-4">
                  {/* Club Logo Slot */}
                  <div className="flex flex-col items-center">
                    <div className="w-16 h-16 flex items-center justify-center border border-slate-200 rounded bg-white p-1 shadow-xs">
                      <img
                        src={currentLetterhead?.club_logo_url || '/assets/permission_page1_img2.png'}
                        alt="Club Logo"
                        className="max-h-full max-w-full object-contain"
                      />
                    </div>
                    <span className="text-[10px] text-slate-500 font-medium mt-1">Club Logo</span>
                  </div>

                  {/* Institute & Club Titles */}
                  <div className="text-center flex-1 px-2">
                    <div className="font-bold text-sm tracking-wide text-slate-800 uppercase">
                      {currentLetterhead?.title_text || "SARDAR VALLABHBHAI NATIONAL INSTITUTE OF TECHNOLOGY, SURAT"}
                    </div>
                    <div className="text-xs font-semibold text-blue-700 uppercase mt-0.5">
                      {currentLetterhead?.subtitle_text || "ASSOCIATION FOR COMPUTING MACHINERY (ACM) STUDENT CHAPTER"}
                    </div>
                    {/* Letterhead Picker Dropdown & Logo by Text */}
                    <div className="mt-2 flex flex-col items-center gap-1.5">
                      {letterheads.length > 0 && (
                        <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 bg-slate-100 hover:bg-slate-200 rounded text-xs text-slate-700 border border-slate-300">
                          <span className="text-[10px] text-slate-500">Letterhead:</span>
                          <select
                            value={selectedLetterheadId || currentLetterhead?.id || ''}
                            onChange={e => {
                              setSelectedLetterheadId(e.target.value);
                              setSaveStatus('unsaved');
                              triggerAutosave();
                            }}
                            className="bg-transparent font-medium text-xs text-slate-800 focus:outline-none cursor-pointer"
                          >
                            {letterheads.map(lh => (
                              <option key={lh.id} value={lh.id}>
                                {lh.name}
                              </option>
                            ))}
                          </select>
                        </div>
                      )}

                      {/* Logo by text helper */}
                      <div className="inline-flex items-center gap-1 text-[11px]">
                        <input
                          type="text"
                          placeholder="e.g. use the ACM logo on the left"
                          value={logoSearchText}
                          onChange={(e) => setLogoSearchText(e.target.value)}
                          className="px-2 py-0.5 text-[10px] border border-slate-300 rounded bg-white text-slate-700 w-44 focus:outline-none focus:ring-1 focus:ring-blue-500"
                        />
                        <button
                          type="button"
                          onClick={handleResolveLogoText}
                          disabled={searchingLogo || !logoSearchText.trim()}
                          className="px-2 py-0.5 bg-blue-600 hover:bg-blue-700 text-white rounded text-[10px] font-medium disabled:opacity-50 transition-colors"
                        >
                          {searchingLogo ? "Searching..." : "Set Logo"}
                        </button>
                      </div>
                      {logoSearchMsg && (
                        <div className="text-[9px] text-slate-500">{logoSearchMsg}</div>
                      )}
                    </div>
                  </div>

                  {/* Locked SVNIT Crest Slot */}
                  <div className="flex flex-col items-center">
                    <div className="w-16 h-16 flex items-center justify-center border border-blue-200 rounded bg-blue-50/30 p-1 shadow-xs relative">
                      <img
                        src={currentLetterhead?.svnit_logo_url || '/assets/permission_page1_img1.png'}
                        alt="SVNIT Emblem"
                        className="max-h-full max-w-full object-contain"
                      />
                      <span className="absolute -top-1.5 -right-1.5 px-1 py-0.2 bg-blue-600 text-white text-[8px] font-bold rounded-full">
                        🔒
                      </span>
                    </div>
                    <span className="text-[10px] text-blue-700 font-medium mt-1">SVNIT (Locked)</span>
                  </div>
                </div>
              );
            })()}

            {/* TipTap Editor Prose */}
            <EditorContent
              editor={editor}
              className="prose prose-slate max-w-none focus:outline-none min-h-[600px] font-serif text-[15px] leading-relaxed"
            />
          </div>
        </div>

        {/* Right Sidebar: Fields Panel (30%) */}
        <div className="w-80 bg-white border-l border-slate-200 flex flex-col h-full shadow-sm">
          <div className="p-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
            <div>
              <h3 className="font-bold text-sm text-slate-800">Fields Panel</h3>
              <p className="text-[11px] text-slate-500">{fields.length} variables defined</p>
            </div>
            <button
              onClick={() => setShowAddFieldModal(true)}
              className="flex items-center gap-1 px-2.5 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded text-xs font-semibold shadow-sm transition-colors"
            >
              <Plus className="w-3.5 h-3.5" />
              Add Field
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-3 space-y-3">
            {fields.map(f => (
              <div key={f.key} className="p-3 border border-slate-200 rounded-lg bg-white shadow-xs hover:border-slate-300 transition-colors">
                <div className="flex items-center justify-between mb-1.5">
                  {editingFieldKey === f.key ? (
                    <div className="flex items-center gap-1 flex-1 mr-2">
                      <input
                        type="text"
                        value={renamedKeyVal}
                        onChange={e => setRenamedKeyVal(e.target.value)}
                        className="text-xs border border-blue-500 rounded px-1.5 py-0.5 flex-1 font-mono focus:outline-none"
                        autoFocus
                      />
                      <button
                        onClick={() => handleRenameField(f.key)}
                        className="p-1 rounded bg-blue-600 text-white hover:bg-blue-700"
                        title="Save Rename"
                      >
                        <Check className="w-3 h-3" />
                      </button>
                      <button
                        onClick={() => setEditingFieldKey(null)}
                        className="p-1 rounded bg-slate-200 text-slate-600 hover:bg-slate-300"
                        title="Cancel"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    </div>
                  ) : (
                    <div className="flex items-center gap-1.5 flex-1 overflow-hidden">
                      <span className="font-mono text-xs font-bold text-indigo-700 truncate">{f.key}</span>
                      {(f as any).ai_suggested && (
                        <span className="text-[9px] bg-purple-100 text-purple-700 font-semibold px-2 py-0.5 rounded-full border border-purple-200 shadow-2xs inline-flex items-center gap-1">
                          <span>AI-suggested</span>
                          <button
                            type="button"
                            title="Mark field as reviewed"
                            data-testid={`review-field-${f.key}`}
                            onClick={() => handleReviewItem(f.key)}
                            className="hover:text-emerald-700 hover:font-bold ml-0.5 text-purple-800"
                          >
                            <Check className="w-2.5 h-2.5" />
                          </button>
                        </span>
                      )}
                      <button
                        onClick={() => {
                          setEditingFieldKey(f.key);
                          setRenamedKeyVal(f.key);
                        }}
                        className="text-[10px] text-slate-400 hover:text-blue-600 underline"
                        title="Rename field (updates all chips)"
                      >
                        rename
                      </button>
                    </div>
                  )}

                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => insertFieldChip(f.key, f.label, f.type)}
                      className="px-2 py-0.5 rounded bg-indigo-50 hover:bg-indigo-100 text-indigo-700 text-[10px] font-semibold border border-indigo-200"
                      title="Insert chip at cursor position"
                    >
                      + Chip
                    </button>
                    <button
                      onClick={() => removeField(f.key)}
                      className="p-1 text-slate-400 hover:text-red-600 rounded"
                      title="Delete field"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                </div>

                {/* Field Settings */}
                <div className="space-y-1.5 text-xs text-slate-600 mt-2 pt-2 border-t border-slate-100">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] text-slate-500">Type:</span>
                    <select
                      value={f.type}
                      onChange={e => {
                        const newType = e.target.value;
                        setFields(fields.map(item => item.key === f.key ? { ...item, type: newType, ai_suggested: false } : item));
                        triggerAutosave();
                      }}
                      className="text-xs border border-slate-200 rounded px-1.5 py-0.5 bg-white font-medium focus:outline-none"
                    >
                      <option value="text">text</option>
                      <option value="longtext">longtext</option>
                      <option value="int">int</option>
                      <option value="money">money (INR)</option>
                      <option value="date">date (DD/MM/YYYY)</option>
                      <option value="date_range">date_range</option>
                      <option value="time_range">time_range</option>
                      <option value="enum">enum</option>
                      <option value="person_ref">person_ref</option>
                      <option value="table">table (repeating)</option>
                    </select>
                  </div>

                  <div className="flex items-center justify-between">
                    <span className="text-[11px] text-slate-500">Required:</span>
                    <input
                      type="checkbox"
                      checked={f.required}
                      onChange={e => {
                        const isReq = e.target.checked;
                        setFields(fields.map(item => item.key === f.key ? { ...item, required: isReq, ai_suggested: false } : item));
                        triggerAutosave();
                      }}
                      className="rounded border-slate-300 text-blue-600 focus:ring-0 cursor-pointer"
                    />
                  </div>

                  <div className="flex items-center justify-between">
                    <span className="text-[11px] text-slate-500">Defer OK:</span>
                    <input
                      type="checkbox"
                      checked={Boolean(f.defer_ok)}
                      onChange={e => {
                        const isDef = e.target.checked;
                        setFields(fields.map(item => item.key === f.key ? { ...item, defer_ok: isDef, ai_suggested: false } : item));
                        triggerAutosave();
                      }}
                      className="rounded border-slate-300 text-blue-600 focus:ring-0 cursor-pointer"
                    />
                  </div>

                  <div className="flex items-center justify-between">
                    <span className="text-[11px] text-slate-500">Sensitive:</span>
                    <input
                      type="checkbox"
                      checked={Boolean(f.sensitive)}
                      onChange={e => {
                        const isSens = e.target.checked;
                        setFields(fields.map(item => item.key === f.key ? { ...item, sensitive: isSens, ai_suggested: false } : item));
                        triggerAutosave();
                      }}
                      className="rounded border-slate-300 text-blue-600 focus:ring-0 cursor-pointer"
                    />
                  </div>

                  <div>
                    <input
                      type="text"
                      placeholder="Ask prompt / description"
                      value={f.ask || ''}
                      onChange={e => {
                        const askVal = e.target.value;
                        setFields(fields.map(item => item.key === f.key ? { ...item, ask: askVal, ai_suggested: false } : item));
                        triggerAutosave();
                      }}
                      className="w-full text-[11px] border border-slate-200 rounded px-1.5 py-0.5 bg-slate-50 focus:bg-white focus:outline-none"
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Add Field Modal */}
      {showAddFieldModal && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-sm w-full p-5 border border-slate-200 animate-in fade-in zoom-in-95 duration-100">
            <h4 className="font-bold text-base text-slate-900 mb-1">Add Template Field</h4>
            <p className="text-xs text-slate-500 mb-4">Creates a field and inserts a pill chip at your cursor position.</p>

            <form onSubmit={handleAddField} className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Field Label / Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Event Venue"
                  value={newFieldName}
                  onChange={e => setNewFieldName(e.target.value)}
                  className="w-full border border-slate-300 rounded-lg px-3 py-1.5 text-xs focus:border-blue-600 focus:outline-none"
                  autoFocus
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Field Type</label>
                <select
                  value={newFieldType}
                  onChange={e => setNewFieldType(e.target.value)}
                  className="w-full border border-slate-300 rounded-lg px-3 py-1.5 text-xs bg-white focus:border-blue-600 focus:outline-none"
                >
                  <option value="text">text (single line)</option>
                  <option value="longtext">longtext (multiline)</option>
                  <option value="int">int (integer count)</option>
                  <option value="money">money (INR with Indian grouping)</option>
                  <option value="date">date (DD/MM/YYYY)</option>
                  <option value="date_range">date_range</option>
                  <option value="time_range">time_range</option>
                  <option value="enum">enum (dropdown options)</option>
                  <option value="person_ref">person_ref (club role)</option>
                  <option value="table">table (repeating items)</option>
                </select>
              </div>

              <div className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  id="req_cb"
                  checked={newFieldRequired}
                  onChange={e => setNewFieldRequired(e.target.checked)}
                  className="rounded border-slate-300 text-blue-600 focus:ring-0 cursor-pointer"
                />
                <label htmlFor="req_cb" className="text-xs text-slate-700 cursor-pointer">
                  Required field (cannot be empty)
                </label>
              </div>

              <div className="flex items-center justify-end gap-2 pt-3">
                <button
                  type="button"
                  onClick={() => setShowAddFieldModal(false)}
                  className="px-3 py-1.5 rounded-lg border border-slate-300 text-slate-600 text-xs font-semibold hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold shadow-sm"
                >
                  Create & Insert Chip
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Live Preview Modal */}
      {showPreviewModal && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-6">
          <div className="bg-white rounded-2xl shadow-2xl max-w-4xl w-full max-h-[90vh] flex flex-col border border-slate-200">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50 rounded-t-2xl">
              <div>
                <h4 className="font-bold text-base text-slate-900">Document Live Preview</h4>
                <p className="text-xs text-slate-500">Rendered via LibreOffice using synthetic dummy data.</p>
              </div>
              <button
                onClick={() => setShowPreviewModal(false)}
                className="p-1 rounded-lg border border-slate-200 hover:bg-slate-100 text-slate-500"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-6 bg-slate-100 flex flex-col items-center gap-6">
              {previewLoading ? (
                <div className="flex flex-col items-center justify-center py-24 gap-3">
                  <RefreshCw className="w-8 h-8 text-blue-600 animate-spin" />
                  <p className="text-sm font-medium text-slate-600">Rendering preview with LibreOffice...</p>
                </div>
              ) : previewPages.length > 0 ? (
                previewPages.map((pageSrc, idx) => (
                  <div key={idx} className="bg-white p-2 border border-slate-300 rounded shadow-md max-w-2xl w-full">
                    <img
                      src={pageSrc}
                      alt={`Preview Page ${idx + 1}`}
                      className="w-full h-auto object-contain rounded"
                    />
                    <p className="text-center text-xs text-slate-400 mt-2">Page {idx + 1} of {previewPages.length}</p>
                  </div>
                ))
              ) : (
                <div className="py-20 text-center text-sm text-slate-500">No preview generated.</div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Validation Report Modal */}
      {showValidationModal && validationReport && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-5 border border-slate-200">
            <div className="flex items-center gap-3 mb-3">
              {validationReport.is_valid ? (
                <div className="w-10 h-10 rounded-full bg-emerald-100 flex items-center justify-center text-emerald-600">
                  <CheckCircle2 className="w-6 h-6" />
                </div>
              ) : (
                <div className="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center text-red-600">
                  <AlertCircle className="w-6 h-6" />
                </div>
              )}
              <div>
                <h4 className="font-bold text-base text-slate-900">
                  {validationReport.is_valid ? 'Validation Passed' : 'Validation Failed'}
                </h4>
                <p className="text-xs text-slate-500">
                  {validationReport.is_valid ? 'Template compiled cleanly without errors.' : 'Errors must be resolved before publishing.'}
                </p>
              </div>
            </div>

            {validationReport.errors && validationReport.errors.length > 0 && (
              <div className="mb-3 p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-800 space-y-1">
                <span className="font-bold block">Errors:</span>
                {validationReport.errors.map((err: string, i: number) => (
                  <p key={i}>• {err}</p>
                ))}
              </div>
            )}

            {validationReport.warnings && validationReport.warnings.length > 0 && (
              <div className="mb-3 p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-800 space-y-1">
                <span className="font-bold block">Warnings:</span>
                {validationReport.warnings.map((w: string, i: number) => (
                  <p key={i}>• {w}</p>
                ))}
              </div>
            )}

            {validationReport.stats && (
              <div className="text-xs text-slate-600 bg-slate-50 p-2.5 rounded border border-slate-200 space-y-0.5">
                <p>Paragraphs: <span className="font-bold">{validationReport.stats.paragraphs}</span></p>
                <p>Tables: <span className="font-bold">{validationReport.stats.tables}</span></p>
                <p>Docx Tags: <span className="font-mono text-[11px]">{validationReport.stats.docx_tags?.join(', ') || 'none'}</span></p>
              </div>
            )}

            <div className="mt-4 flex justify-end">
              <button
                onClick={() => setShowValidationModal(false)}
                className="px-4 py-1.5 bg-slate-800 hover:bg-slate-900 text-white rounded-lg text-xs font-semibold"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Review All Confirmation Modal */}
      {showReviewAllConfirm && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6 border border-slate-200">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center text-blue-600">
                <Check className="w-6 h-6" />
              </div>
              <div>
                <h4 className="font-bold text-base text-slate-900">Review All AI Suggestions</h4>
                <p className="text-xs text-slate-500">Confirm acceptance of all AI-generated fields and blocks.</p>
              </div>
            </div>

            <p className="text-xs text-slate-600 mb-4 leading-relaxed">
              Reviewing clears the AI-suggested flag from all fields and layout blocks so this template can be published. You can still modify any content afterwards.
            </p>

            <div className="max-h-48 overflow-y-auto bg-slate-50 border border-slate-200 rounded-lg p-3 text-xs space-y-1 mb-4">
              <span className="font-bold text-slate-700 block mb-1">Items to be accepted:</span>
              {fields.filter(f => (f as any).ai_suggested).map(f => (
                <div key={f.key} className="flex items-center justify-between text-slate-600">
                  <span>Field: <strong className="font-mono">{f.key}</strong> ({f.label})</span>
                  <span className="text-[10px] text-purple-700 bg-purple-50 px-1.5 py-0.5 rounded">field</span>
                </div>
              ))}
              {(template?.editor_json?.content || []).filter((b: any) => b.ai_suggested || b.attrs?.ai_suggested).map((b: any, idx: number) => (
                <div key={idx} className="flex items-center justify-between text-slate-600">
                  <span>Block: <strong className="capitalize">{b.type}</strong> (#{idx + 1})</span>
                  <span className="text-[10px] text-blue-700 bg-blue-50 px-1.5 py-0.5 rounded">block</span>
                </div>
              ))}
            </div>

            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowReviewAllConfirm(false)}
                className="px-4 py-2 text-xs font-semibold text-slate-600 hover:text-slate-800"
              >
                Cancel
              </button>
              <button
                type="button"
                data-testid="confirm-review-all-btn"
                onClick={handleReviewAll}
                disabled={reviewingAi}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-bold transition-colors shadow-xs"
              >
                {reviewingAi ? 'Reviewing...' : 'Accept All & Mark Reviewed'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Unreviewed AI Items Gate Modal (on Publish 409) */}
      {unreviewedModal && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6 border border-amber-300">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-10 h-10 rounded-full bg-amber-100 flex items-center justify-center text-amber-700">
                <AlertCircle className="w-6 h-6" />
              </div>
              <div>
                <h4 className="font-bold text-base text-slate-900">Unreviewed AI Content</h4>
                <p className="text-xs text-amber-800 font-medium">Review required before publishing</p>
              </div>
            </div>

            <p className="text-xs text-slate-600 mb-3 leading-relaxed">
              This template contains {unreviewedModal.length} AI-suggested item(s) that must be reviewed and accepted by a club editor/owner before the template can be published.
            </p>

            <div className="max-h-48 overflow-y-auto bg-amber-50/60 border border-amber-200 rounded-lg p-3 text-xs space-y-1.5 mb-4">
              {unreviewedModal.map((item, idx) => (
                <div key={idx} className="flex items-center justify-between text-slate-700">
                  <span className="truncate max-w-[260px]">• {item.description || item.label || item.key}</span>
                  <span className="text-[10px] bg-amber-200/80 text-amber-900 font-bold px-1.5 py-0.5 rounded uppercase">
                    {item.type}
                  </span>
                </div>
              ))}
            </div>

            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setUnreviewedModal(null)}
                className="px-4 py-2 text-xs font-semibold text-slate-600 hover:text-slate-800"
              >
                Review Manually
              </button>
              <button
                type="button"
                data-testid="gate-review-all-and-publish-btn"
                onClick={async () => {
                  await handleReviewAll();
                  await handlePublish();
                }}
                disabled={reviewingAi || saving}
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-bold transition-colors shadow-xs"
              >
                {reviewingAi ? 'Reviewing...' : 'Review All & Publish'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
