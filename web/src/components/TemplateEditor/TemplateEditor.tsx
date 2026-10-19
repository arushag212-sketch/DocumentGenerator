import React, { useState, useEffect, useRef } from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import TextAlign from '@tiptap/extension-text-align';
import Underline from '@tiptap/extension-underline';
import { NodeSelection } from '@tiptap/pm/state';
import {
  ArrowLeft, Save, Eye, CheckCircle2, AlertCircle, RefreshCw,
  Bold as BoldIcon, Italic as ItalicIcon, Underline as UnderlineIcon,
  AlignLeft, AlignCenter, AlignRight, AlignJustify, List, ListOrdered,
  Plus, Table as TableIcon, FileText, Check, X, Sparkles,
  Rows, Columns, SplitSquareVertical, Tag, Image as ImageIcon, ImagePlus,
  Bot, Trash2, GripVertical
} from 'lucide-react';
import { api } from '../../api/client';
import {
  CustomTable,
  CustomTableRow,
  CustomTableCell,
  CustomTableHeader,
  AiSuggestedBlock,
  FieldChip,
  ImageBlock,
  PageBreak,
  insertInfoTable,
  insertRepeatingTable,
  insertSignatureGrid,
  insertImageBlock,
  insertFieldChip,
  migrateTipTapContent,
} from './extensions';

interface TemplateField {
  key: string;
  label: string;
  type: string;
  required: boolean;
  importance?: 'essential' | 'optional';
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
  /** Optional integration seam for a future assistant/chat panel. */
  assistantSlot?: React.ReactNode | ((context: TemplateAssistantContext) => React.ReactNode);
  /** Logo options can be supplied by an embedding page; the editor also loads club assets by default. */
  clubLogoOptions?: ClubLogoOption[];
}

export interface ClubLogoOption {
  id: string;
  name: string;
  url: string;
  alt?: string;
  kind?: string;
}

export interface TemplateAssistantContext {
  clubId: string;
  templateId: string;
  editor: any;
  template: any;
  fields: TemplateField[];
  insertField: (fieldKey: string) => void;
}

// ---------------------------------------------------------------------------
// Error Boundary
// ---------------------------------------------------------------------------

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

class EditorErrorBoundary extends React.Component<{ children: React.ReactNode }, ErrorBoundaryState> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: any) {
    console.error('Editor Error Boundary caught an error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="p-8 max-w-lg mx-auto my-12 bg-white rounded-lg shadow-lg border border-red-200 text-center">
          <div className="w-12 h-12 mx-auto mb-4 text-red-500 bg-red-100 rounded-full flex items-center justify-center">
            <AlertCircle className="w-6 h-6" />
          </div>
          <h2 className="text-lg font-bold text-slate-800 mb-2">Editor Encountered a Problem</h2>
          <p className="text-sm text-slate-600 mb-6">
            Something went wrong while rendering the document editor.
          </p>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-medium text-sm rounded shadow-sm transition"
          >
            Reload Editor
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

function findNodePosition(view: any, pos: number, nodeName: string): number | null {
  const doc = view?.state?.doc;
  if (!doc || typeof pos !== 'number') return null;

  for (const candidatePos of [pos, pos - 1]) {
    if (candidatePos >= 0) {
      const candidate = doc.nodeAt(candidatePos);
      if (candidate?.type?.name === nodeName) return candidatePos;
    }
  }

  try {
    const resolved = doc.resolve(Math.max(0, Math.min(pos, doc.content.size)));
    for (let depth = resolved.depth; depth > 0; depth -= 1) {
      if (resolved.node(depth).type.name === nodeName) return resolved.before(depth);
    }
  } catch {
    // A stale click position can occur while a transaction is being applied.
  }
  return null;
}

/** Resolve the pointer to a ProseMirror position, keeping block drops outside table cells. */
function getDropPosition(editor: any, event: React.DragEvent<HTMLElement>): number | null {
  if (!editor?.view) return null;
  const coords = editor.view.posAtCoords({ left: event.clientX, top: event.clientY });
  if (!coords || typeof coords.pos !== 'number') return null;

  try {
    const resolved = editor.state.doc.resolve(coords.pos);
    const topIndex = resolved.index(0);
    const topNode = editor.state.doc.child(topIndex);
    const blockNodeNames = new Set(['table', 'imageBlock', 'pageBreak']);
    let ancestorIsBlock = false;
    for (let depth = resolved.depth; depth > 0; depth -= 1) {
      if (blockNodeNames.has(resolved.node(depth).type.name)) {
        ancestorIsBlock = true;
        break;
      }
    }

    if (ancestorIsBlock && topNode) {
      let topStart = 0;
      for (let index = 0; index < topIndex; index += 1) {
        topStart += editor.state.doc.child(index).nodeSize;
      }
      const dom = editor.view.nodeDOM(topStart) as HTMLElement | null;
      const rect = dom?.getBoundingClientRect?.();
      if (rect) {
        return event.clientY < rect.top + rect.height / 2 ? topStart : topStart + topNode.nodeSize;
      }
      return topStart + topNode.nodeSize;
    }
  } catch {
    // Fall back to TipTap's resolved coordinate when the document changed.
  }
  return coords.pos;
}

// ---------------------------------------------------------------------------
// Main Template Editor Component
// ---------------------------------------------------------------------------

export const TemplateEditor: React.FC<TemplateEditorProps> = ({
  clubId,
  templateId,
  onBack,
  assistantSlot,
  clubLogoOptions: providedClubLogoOptions,
}) => {
  const [template, setTemplate] = useState<any>(null);
  const [fields, setFields] = useState<TemplateField[]>([]);
  const [letterheads, setLetterheads] = useState<any[]>([]);
  const [clubLogoOptions, setClubLogoOptions] = useState<ClubLogoOption[]>(providedClubLogoOptions || []);
  const [selectedLetterheadId, setSelectedLetterheadId] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<'saved' | 'saving' | 'unsaved'>('saved');
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewPages, setPreviewPages] = useState<string[]>([]);
  const [showPreviewModal, setShowPreviewModal] = useState(false);
  const [validationReport, setValidationReport] = useState<any>(null);
  const [showValidationModal, setShowValidationModal] = useState(false);

  // Field Management Modals
  const [newFieldName, setNewFieldName] = useState('');
  const [newFieldType, setNewFieldType] = useState('text');
  const [newFieldRequired, setNewFieldRequired] = useState(true);
  const [showAddFieldModal, setShowAddFieldModal] = useState(false);

  // Slash Command Menu State
  const [showSlashMenu, setShowSlashMenu] = useState(false);
  const [slashMenuIndex, setSlashMenuIndex] = useState(0);

  // Selection Bubble Menu State
  const [bubblePos, setBubblePos] = useState<{ top: number; left: number } | null>(null);

  // Field Chip Popover State
  const [chipPopover, setChipPopover] = useState<{
    top: number;
    left: number;
    position: number;
    fieldName: string;
    label: string;
    fieldType: string;
    ask: string;
    importance: 'essential' | 'optional';
    required: boolean;
    sensitive: boolean;
  } | null>(null);

  // AI Review Gate State
  const [unreviewedModal, setUnreviewedModal] = useState<any[] | null>(null);
  const [reviewingAi, setReviewingAi] = useState(false);
  const [dragOverCanvas, setDragOverCanvas] = useState(false);
  const [dropIndicator, setDropIndicator] = useState<{ top: number; left: number; width: number } | null>(null);
  const [selectedImageBlock, setSelectedImageBlock] = useState<{
    position: number;
    attrs: Record<string, any>;
  } | null>(null);

  const autosaveTimerRef = useRef<any>(null);
  const contentLoadedRef = useRef<boolean>(false);
  const canvasRef = useRef<HTMLDivElement | null>(null);

  // TipTap Editor instance
  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: { levels: [1, 2, 3] },
      }),
      TextAlign.configure({
        types: ['heading', 'paragraph'],
      }),
      Underline,
      CustomTable.configure({
        resizable: true,
      }),
      CustomTableRow,
      CustomTableCell,
      CustomTableHeader,
      AiSuggestedBlock,
      FieldChip,
      ImageBlock,
      PageBreak,
    ],
    editorProps: {
      handleClick: (view, pos, event) => {
        const target = event.target as HTMLElement;
        const imageTarget = target.closest('.image-block');
        const imagePosition = imageTarget ? findNodePosition(view, pos, 'imageBlock') : null;
        if (imagePosition !== null) {
          const imageNode = view.state.doc.nodeAt(imagePosition);
          if (imageNode) {
            view.dispatch(view.state.tr.setSelection(NodeSelection.create(view.state.doc, imagePosition)));
            setSelectedImageBlock({ position: imagePosition, attrs: { ...imageNode.attrs } });
            setChipPopover(null);
            setBubblePos(null);
            return true;
          }
        }

        const fieldTarget = target.closest('.field-chip');
        const fieldPosition = fieldTarget ? findNodePosition(view, pos, 'fieldChip') : null;
        if (fieldPosition !== null) {
          const rect = (fieldTarget || target).getBoundingClientRect();
          const node = view.state.doc.nodeAt(fieldPosition);
          const attrs = node?.type.name === 'fieldChip' ? node.attrs : {};
          const fieldName = attrs.fieldName || fieldTarget?.getAttribute('data-field-name') || '';
          const label = attrs.label || fieldTarget?.getAttribute('data-label') || fieldName;
          const fieldType = attrs.fieldType || fieldTarget?.getAttribute('data-field-type') || 'text';
          const ask = attrs.ask || fieldTarget?.getAttribute('data-ask') || `Please provide ${label}`;
          const importance = (attrs.importance || fieldTarget?.getAttribute('data-importance') || 'optional') as 'essential' | 'optional';
          const required = importance === 'essential' || attrs.required || fieldTarget?.getAttribute('data-required') === 'true';
          const sensitive = attrs.sensitive || fieldTarget?.getAttribute('data-sensitive') === 'true';

          view.dispatch(view.state.tr.setSelection(NodeSelection.create(view.state.doc, fieldPosition)));
          setChipPopover({
            top: Math.min(rect.bottom + 8, window.innerHeight - 320),
            left: Math.min(Math.max(rect.left, 20), window.innerWidth - 340),
            position: fieldPosition,
            fieldName,
            label,
            fieldType,
            ask,
            importance,
            required,
            sensitive,
          });
          setSelectedImageBlock(null);
          return true;
        } else {
          setChipPopover(null);
          setSelectedImageBlock(null);
        }
        return false;
      },
      handleKeyDown: (_view, event) => {
        if (event.key === 'Escape') {
          setChipPopover(null);
          setSelectedImageBlock(null);
          setShowSlashMenu(false);
        }
        return false;
      },
    },
    content: { type: 'doc', content: [] },
    onSelectionUpdate: ({ editor: currentEditor }) => {
      const { selection } = currentEditor.state;
      if (selection instanceof NodeSelection && selection.node?.type.name === 'imageBlock') {
        setSelectedImageBlock({ position: selection.from, attrs: { ...selection.node.attrs } });
        setChipPopover(null);
        setBubblePos(null);
        return;
      }
      if (selection instanceof NodeSelection && selection.node?.type.name === 'fieldChip') {
        setBubblePos(null);
        return;
      }
      if (selection instanceof NodeSelection && selection.node?.type.name !== 'fieldChip') {
        setSelectedImageBlock(null);
      }
      if (!selection || selection.empty) {
        setBubblePos(null);
        return;
      }
      try {
        const coords = currentEditor.view.coordsAtPos(selection.from);
        setBubblePos({
          top: Math.max(coords.top - 44, 10),
          left: Math.min(Math.max(coords.left, 20), Math.max(20, window.innerWidth - 240)),
        });
      } catch {
        setBubblePos(null);
      }
    },
    onBlur: () => {
      setBubblePos(null);
    },
    onUpdate: ({ editor: currentEditor, transaction }: any) => {
      setSaveStatus('unsaved');
      triggerAutosave();

      // Check for slash command at the start of empty line
      const { selection } = currentEditor.state;
      const { $from } = selection;
      const textBefore = $from.parent.textBetween(0, $from.parentOffset, undefined, '\ufffc');
      if (textBefore === '/') {
        setShowSlashMenu(true);
        setSlashMenuIndex(0);
      } else if (showSlashMenu) {
        setShowSlashMenu(false);
      }

      // Clear AI flag on edited paragraph
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

  // Logo assets are intentionally loaded through the existing club-scoped
  // asset endpoint. Embedders can provide a curated list when they already
  // have one; an unavailable asset simply leaves a descriptive placeholder.
  useEffect(() => {
    let isMounted = true;
    if (providedClubLogoOptions) {
      setClubLogoOptions(providedClubLogoOptions);
      return () => {
        isMounted = false;
      };
    }

    api.clubs
      .getAssets(clubId)
      .then((assets: any[]) => {
        if (!isMounted) return;
        const logoAssets = (assets || [])
          .filter((asset) => asset?.kind === 'logo' || String(asset?.mime || '').startsWith('image/'))
          .map((asset) => ({
            id: String(asset.id),
            name: asset.filename || 'Club logo',
            url: asset.url || `/api/v1/assets/${asset.id}/content`,
            alt: asset.filename || 'Club logo',
            kind: asset.kind,
          }));
        setClubLogoOptions(logoAssets);
      })
      .catch(() => {
        // Asset permissions should not prevent the editor from loading.
        if (isMounted) setClubLogoOptions([]);
      });

    return () => {
      isMounted = false;
    };
  }, [clubId, providedClubLogoOptions]);

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

        if (editor && draftData.editor_json && !contentLoadedRef.current) {
          editor.commands.setContent(migrateTipTapContent(draftData.editor_json));
          contentLoadedRef.current = true;
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

  // Sync editor content ONCE if template loaded before editor was ready
  useEffect(() => {
    if (editor && template?.editor_json && !contentLoadedRef.current) {
      editor.commands.setContent(migrateTipTapContent(template.editor_json));
      contentLoadedRef.current = true;
    }
  }, [editor, template]);

  // Debounced Autosave (1s)
  const triggerAutosave = () => {
    if (autosaveTimerRef.current) clearTimeout(autosaveTimerRef.current);
    autosaveTimerRef.current = setTimeout(() => {
      handleSave(false);
    }, 1000);
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

  // Review All AI items
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
      setUnreviewedModal(null);
      setSaveStatus('unsaved');
      triggerAutosave();
    } catch (err: any) {
      alert(err.message || 'Failed to review all items');
    } finally {
      setReviewingAi(false);
    }
  };

  // Add new field
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
      importance: newFieldRequired ? 'essential' : 'optional',
      ask: `Enter ${newFieldName.trim()}`,
      defer_ok: false,
      sensitive: false,
    };

    const nextFields = [...fields, newF];
    setFields(nextFields);
    insertFieldChip(
      editor,
      cleanKey,
      newF.label,
      newF.type,
      newF.ask,
      newF.importance,
      newF.required,
      false
    );
    setNewFieldName('');
    setShowAddFieldModal(false);
    triggerAutosave();
  };

  const handleToggleChipRequired = (newReq: boolean) => {
    if (!chipPopover || !editor) return;
    const newImp = newReq ? 'essential' : 'optional';
    const tr = editor.state.tr;
    editor.state.doc.descendants((node, pos) => {
      if (node.type.name === 'fieldChip' && node.attrs.fieldName === chipPopover.fieldName) {
        tr.setNodeMarkup(pos, undefined, {
          ...node.attrs,
          importance: newImp,
          required: newReq,
        });
      }
    });
    editor.view.dispatch(tr);
    setFields((prev) =>
      prev.map((f) =>
        f.key === chipPopover.fieldName
          ? { ...f, importance: newImp, required: newReq }
          : f
      )
    );
    setChipPopover((prev) => (prev ? { ...prev, importance: newImp, required: newReq } : null));
    setSaveStatus('unsaved');
    triggerAutosave();
  };

  const handleToggleChipSensitive = (newSens: boolean) => {
    if (!chipPopover || !editor) return;
    const tr = editor.state.tr;
    editor.state.doc.descendants((node, pos) => {
      if (node.type.name === 'fieldChip' && node.attrs.fieldName === chipPopover.fieldName) {
        tr.setNodeMarkup(pos, undefined, {
          ...node.attrs,
          sensitive: newSens,
        });
      }
    });
    editor.view.dispatch(tr);
    setFields((prev) =>
      prev.map((f) =>
        f.key === chipPopover.fieldName
          ? { ...f, sensitive: newSens }
          : f
      )
    );
    setChipPopover((prev) => (prev ? { ...prev, sensitive: newSens } : null));
    setSaveStatus('unsaved');
    triggerAutosave();
  };

  const handleUpdateChip = (updates: Partial<{ label: string; fieldType: string; ask: string }>) => {
    if (!chipPopover || !editor) return;
    const next = { ...chipPopover, ...updates };
    const tr = editor.state.tr;
    editor.state.doc.descendants((node, pos) => {
      if (node.type.name === 'fieldChip' && node.attrs.fieldName === chipPopover.fieldName) {
        tr.setNodeMarkup(pos, undefined, {
          ...node.attrs,
          ...(updates.label !== undefined ? { label: updates.label } : {}),
          ...(updates.fieldType !== undefined ? { fieldType: updates.fieldType } : {}),
          ...(updates.ask !== undefined ? { ask: updates.ask } : {}),
        });
      }
    });
    editor.view.dispatch(tr);
    setFields((prev) =>
      prev.map((field) =>
        field.key === chipPopover.fieldName
          ? {
              ...field,
              ...(updates.label !== undefined ? { label: updates.label } : {}),
              ...(updates.fieldType !== undefined ? { type: updates.fieldType } : {}),
              ...(updates.ask !== undefined ? { ask: updates.ask } : {}),
            }
          : field
      )
    );
    setChipPopover(next);
    setSaveStatus('unsaved');
    triggerAutosave();
  };

  const handleDeleteChip = () => {
    if (!chipPopover || !editor) return;
    editor.chain().focus().setNodeSelection(chipPopover.position).deleteSelection().run();
    setChipPopover(null);
    setSaveStatus('unsaved');
    triggerAutosave();
  };

  const updateImageBlock = (updates: Record<string, any>) => {
    if (!selectedImageBlock || !editor) return;
    const nextAttrs = { ...selectedImageBlock.attrs, ...updates };
    editor
      .chain()
      .setNodeSelection(selectedImageBlock.position)
      .updateAttributes('imageBlock', updates)
      .run();
    setSelectedImageBlock({ ...selectedImageBlock, attrs: nextAttrs });
    setSaveStatus('unsaved');
    triggerAutosave();
  };

  const selectClubLogo = (assetId: string) => {
    if (!selectedImageBlock) return;
    const asset = clubLogoOptions.find((option) => option.id === assetId);
    if (!assetId || !asset) {
      updateImageBlock({
        imageType: 'club-logo',
        src: '',
        clubLogoAssetId: null,
        logoAssetId: null,
        assetId: null,
        alt: 'Club logo',
        placeholderText: 'Choose a club logo from the asset library',
      });
      return;
    }
    updateImageBlock({
      imageType: 'club-logo',
      src: asset.url,
      clubLogoAssetId: asset.id,
      logoAssetId: asset.id,
      assetId: asset.id,
      alt: asset.alt || asset.name,
      placeholderText: `Selected logo: ${asset.name}`,
    });
  };

  // Slash command options
  const slashOptions = [
    {
      title: 'Heading 2',
      description: 'Section header',
      icon: <span className="font-bold text-xs">H2</span>,
      action: () => {
        editor?.chain().focus().deleteRange({ from: editor.state.selection.from - 1, to: editor.state.selection.from }).setHeading({ level: 2 }).run();
      },
    },
    {
      title: 'Info Table',
      description: '2-column Key-Value Details table',
      icon: <TableIcon className="w-4 h-4 text-indigo-600" />,
      action: () => {
        editor?.chain().focus().deleteRange({ from: editor.state.selection.from - 1, to: editor.state.selection.from }).run();
        insertInfoTable(editor);
      },
    },
    {
      title: 'Repeating Table',
      description: 'Itemized list with columns & computed total',
      icon: <Rows className="w-4 h-4 text-blue-600" />,
      action: () => {
        editor?.chain().focus().deleteRange({ from: editor.state.selection.from - 1, to: editor.state.selection.from }).run();
        insertRepeatingTable(editor);
      },
    },
    {
      title: 'Signature Grid',
      description: 'Designated signers with signature lines',
      icon: <Columns className="w-4 h-4 text-emerald-600" />,
      action: () => {
        editor?.chain().focus().deleteRange({ from: editor.state.selection.from - 1, to: editor.state.selection.from }).run();
        insertSignatureGrid(editor, 2);
      },
    },
    {
      title: 'Generic Table',
      description: 'Standard 3x3 table',
      icon: <TableIcon className="w-4 h-4 text-slate-600" />,
      action: () => {
        editor?.chain().focus().deleteRange({ from: editor.state.selection.from - 1, to: editor.state.selection.from }).insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run();
      },
    },
    {
      title: 'Insert Field',
      description: 'Insert dynamic field chip',
      icon: <Sparkles className="w-4 h-4 text-amber-500" />,
      action: () => {
        editor?.chain().focus().deleteRange({ from: editor.state.selection.from - 1, to: editor.state.selection.from }).run();
        setShowAddFieldModal(true);
      },
    },
    {
      title: 'Page Break',
      description: 'Split document onto next page',
      icon: <SplitSquareVertical className="w-4 h-4 text-rose-500" />,
      action: () => {
        editor?.chain().focus().deleteRange({ from: editor.state.selection.from - 1, to: editor.state.selection.from }).insertContent({ type: 'pageBreak' }).run();
      },
    },
    {
      title: 'Club Logo',
      description: 'Place a selectable club-logo block',
      icon: <ImageIcon className="w-4 h-4 text-emerald-600" />,
      action: () => {
        editor?.chain().focus().deleteRange({ from: editor.state.selection.from - 1, to: editor.state.selection.from }).run();
        insertImageBlock(editor, { imageType: 'club-logo' });
      },
    },
    {
      title: 'Image Placeholder',
      description: 'Reserve space for a document image',
      icon: <ImagePlus className="w-4 h-4 text-sky-600" />,
      action: () => {
        editor?.chain().focus().deleteRange({ from: editor.state.selection.from - 1, to: editor.state.selection.from }).run();
        insertImageBlock(editor, { imageType: 'image' });
      },
    },
  ];

  const blockPalette = [
    { id: 'infoTable', label: 'Info table', description: 'Key-value event details', icon: <TableIcon className="w-4 h-4 text-indigo-600" /> },
    { id: 'repeatingTable', label: 'Repeating table', description: 'Items, amounts and totals', icon: <Rows className="w-4 h-4 text-blue-600" /> },
    { id: 'signatureGrid', label: 'Signature grid', description: 'Signer blocks and lines', icon: <Columns className="w-4 h-4 text-emerald-600" /> },
    { id: 'pageBreak', label: 'Page break', description: 'Start a new page', icon: <SplitSquareVertical className="w-4 h-4 text-rose-500" /> },
    { id: 'clubLogo', label: 'Club logo', description: 'Choose a logo from club assets', icon: <ImageIcon className="w-4 h-4 text-emerald-600" /> },
    { id: 'imageBlock', label: 'Image placeholder', description: 'Reserve a clear image position', icon: <ImagePlus className="w-4 h-4 text-sky-600" /> },
  ];

  const insertDraggedBlock = (blockId: string, position?: number | null) => {
    const dropPosition = typeof position === 'number' ? position : undefined;
    if (dropPosition !== undefined && editor) {
      // Keep the editor's fallback selection aligned with the pointer too;
      // this matters when a block cannot be inserted directly inside a table
      // cell and safeInsertBlock has to choose the nearest valid block slot.
      try {
        editor.commands.setTextSelection(dropPosition);
      } catch {
        // The helper will resolve a safe position if the document changed.
      }
    }
    if (blockId === 'infoTable') insertInfoTable(editor, undefined, dropPosition);
    if (blockId === 'repeatingTable') insertRepeatingTable(editor, undefined, undefined, undefined, dropPosition);
    if (blockId === 'signatureGrid') insertSignatureGrid(editor, 2, undefined, dropPosition);
    if (blockId === 'clubLogo') insertImageBlock(editor, { imageType: 'club-logo' }, dropPosition);
    if (blockId === 'imageBlock') insertImageBlock(editor, { imageType: 'image' }, dropPosition);
    if (blockId === 'pageBreak') {
      const content = { type: 'pageBreak' };
      if (dropPosition !== undefined && editor?.can().insertContentAt(dropPosition, content)) {
        editor.chain().focus().insertContentAt(dropPosition, content).run();
      } else {
        editor?.chain().focus().insertContent(content).run();
      }
    }
    setDragOverCanvas(false);
    setDropIndicator(null);
  };

  const insertFieldForAssistant = (fieldKey: string) => {
    const field = fields.find((candidate) => candidate.key === fieldKey);
    if (!field) return;
    insertFieldChip(
      editor,
      field.key,
      field.label,
      field.type,
      field.ask,
      field.importance || (field.required ? 'essential' : 'optional'),
      field.required,
      field.sensitive
    );
  };

  const assistantContent =
    typeof assistantSlot === 'function'
      ? assistantSlot({
          clubId,
          templateId,
          editor,
          template,
          fields,
          insertField: insertFieldForAssistant,
        })
      : assistantSlot;

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[600px] text-slate-500">
        <RefreshCw className="w-8 h-8 animate-spin mb-3 text-indigo-600" />
        <p className="text-sm font-medium">Loading document template...</p>
      </div>
    );
  }

  return (
    <EditorErrorBoundary>
      <div className="flex flex-col min-h-screen bg-slate-100">
        {/* Top Sticky Header */}
        <header className="sticky top-0 z-30 bg-white border-b border-slate-200 px-6 py-3 flex items-center justify-between shadow-xs">
          <div className="flex items-center gap-4">
            <button
              onClick={onBack}
              className="p-1.5 rounded-md hover:bg-slate-100 text-slate-600 transition"
              title="Back to gallery"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="font-bold text-slate-900 text-base">{template?.name || 'Untitled Template'}</h1>
                <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-slate-100 text-slate-600 border border-slate-200">
                  {template?.category || 'General'}
                </span>
              </div>
              <div className="flex items-center gap-2 mt-0.5 text-xs text-slate-500">
                {/* Autosave Status Indicator */}
                <div className="flex items-center gap-1">
                  {saveStatus === 'saving' && (
                    <>
                      <RefreshCw className="w-3 h-3 animate-spin text-blue-500" />
                      <span className="text-blue-600 font-medium">Saving...</span>
                    </>
                  )}
                  {saveStatus === 'saved' && (
                    <>
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                      <span className="text-emerald-700 font-medium">Saved</span>
                    </>
                  )}
                  {saveStatus === 'unsaved' && (
                    <>
                      <div className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
                      <span className="text-amber-700 font-medium">Unsaved changes</span>
                    </>
                  )}
                </div>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => handleSave(true)}
              disabled={saving}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-slate-700 bg-white border border-slate-300 rounded-md hover:bg-slate-50 shadow-xs transition"
            >
              <Save className="w-4 h-4 text-slate-500" />
              <span>Save</span>
            </button>

            <button
              onClick={handlePreview}
              disabled={previewLoading}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-indigo-700 bg-indigo-50 border border-indigo-200 rounded-md hover:bg-indigo-100 shadow-xs transition"
            >
              {previewLoading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Eye className="w-4 h-4" />}
              <span>Preview</span>
            </button>

            <button
              onClick={handleCompile}
              disabled={saving}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-purple-700 bg-purple-50 border border-purple-200 rounded-md hover:bg-purple-100 shadow-xs transition"
            >
              <FileText className="w-4 h-4" />
              <span>Compile</span>
            </button>

            <button
              onClick={handlePublish}
              disabled={saving}
              className="inline-flex items-center gap-1.5 px-4 py-1.5 text-sm font-medium text-white bg-emerald-600 rounded-md hover:bg-emerald-700 shadow-xs transition"
            >
              <Check className="w-4 h-4" />
              <span>Publish</span>
            </button>
          </div>
        </header>

        {/* Toolbar */}
        <div className="sticky top-[57px] z-20 bg-white/95 backdrop-blur-xs border-b border-slate-200 px-6 py-2 flex flex-wrap items-center gap-2 shadow-xs">
          <div className="flex items-center gap-1 border-r border-slate-200 pr-2">
            <button
              onClick={() => editor?.chain().focus().toggleBold().run()}
              className={`p-1.5 rounded hover:bg-slate-100 ${editor?.isActive('bold') ? 'bg-slate-200 text-indigo-700' : 'text-slate-600'}`}
              title="Bold"
            >
              <BoldIcon className="w-4 h-4" />
            </button>
            <button
              onClick={() => editor?.chain().focus().toggleItalic().run()}
              className={`p-1.5 rounded hover:bg-slate-100 ${editor?.isActive('italic') ? 'bg-slate-200 text-indigo-700' : 'text-slate-600'}`}
              title="Italic"
            >
              <ItalicIcon className="w-4 h-4" />
            </button>
            <button
              onClick={() => editor?.chain().focus().toggleUnderline().run()}
              className={`p-1.5 rounded hover:bg-slate-100 ${editor?.isActive('underline') ? 'bg-slate-200 text-indigo-700' : 'text-slate-600'}`}
              title="Underline"
            >
              <UnderlineIcon className="w-4 h-4" />
            </button>
          </div>

          <div className="flex items-center gap-1 border-r border-slate-200 pr-2">
            <button
              onClick={() => editor?.chain().focus().setTextAlign('left').run()}
              className={`p-1.5 rounded hover:bg-slate-100 ${editor?.isActive({ textAlign: 'left' }) ? 'bg-slate-200 text-indigo-700' : 'text-slate-600'}`}
              title="Align Left"
            >
              <AlignLeft className="w-4 h-4" />
            </button>
            <button
              onClick={() => editor?.chain().focus().setTextAlign('center').run()}
              className={`p-1.5 rounded hover:bg-slate-100 ${editor?.isActive({ textAlign: 'center' }) ? 'bg-slate-200 text-indigo-700' : 'text-slate-600'}`}
              title="Align Center"
            >
              <AlignCenter className="w-4 h-4" />
            </button>
            <button
              onClick={() => editor?.chain().focus().setTextAlign('right').run()}
              className={`p-1.5 rounded hover:bg-slate-100 ${editor?.isActive({ textAlign: 'right' }) ? 'bg-slate-200 text-indigo-700' : 'text-slate-600'}`}
              title="Align Right"
            >
              <AlignRight className="w-4 h-4" />
            </button>
            <button
              onClick={() => editor?.chain().focus().setTextAlign('justify').run()}
              className={`p-1.5 rounded hover:bg-slate-100 ${editor?.isActive({ textAlign: 'justify' }) ? 'bg-slate-200 text-indigo-700' : 'text-slate-600'}`}
              title="Justify"
            >
              <AlignJustify className="w-4 h-4" />
            </button>
          </div>

          <div className="flex items-center gap-1 border-r border-slate-200 pr-2">
            <button
              onClick={() => editor?.chain().focus().toggleBulletList().run()}
              className={`p-1.5 rounded hover:bg-slate-100 ${editor?.isActive('bulletList') ? 'bg-slate-200 text-indigo-700' : 'text-slate-600'}`}
              title="Bullet List"
            >
              <List className="w-4 h-4" />
            </button>
            <button
              onClick={() => editor?.chain().focus().toggleOrderedList().run()}
              className={`p-1.5 rounded hover:bg-slate-100 ${editor?.isActive('orderedList') ? 'bg-slate-200 text-indigo-700' : 'text-slate-600'}`}
              title="Numbered List"
            >
              <ListOrdered className="w-4 h-4" />
            </button>
          </div>

          {/* Block Inserters */}
          <div className="flex items-center gap-1">
            <button
              onClick={() => insertInfoTable(editor)}
              className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded border border-slate-300 transition"
              title="Insert 2-column info table"
            >
              <TableIcon className="w-3.5 h-3.5 text-indigo-600" />
              <span>Info Table</span>
            </button>

            <button
              onClick={() => insertRepeatingTable(editor)}
              className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded border border-slate-300 transition"
              title="Insert repeating items table"
            >
              <Rows className="w-3.5 h-3.5 text-blue-600" />
              <span>Repeating Table</span>
            </button>

            <button
              onClick={() => insertSignatureGrid(editor, 2)}
              className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded border border-slate-300 transition"
              title="Insert signature blocks"
            >
              <Columns className="w-3.5 h-3.5 text-emerald-600" />
              <span>Signatures</span>
            </button>

            <button
              onClick={() => editor?.chain().focus().insertContent({ type: 'pageBreak' }).run()}
              className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded border border-slate-300 transition"
              title="Insert page break"
            >
              <SplitSquareVertical className="w-3.5 h-3.5 text-rose-500" />
              <span>Page Break</span>
            </button>
          </div>

          {/* Table Context Controls (Visible when cursor is inside any table) */}
          {editor?.isActive('table') && (
            <div className="flex items-center gap-1 bg-blue-50 border border-blue-200 rounded px-2 py-0.5 ml-auto text-xs text-blue-900">
              <span className="font-semibold text-blue-800 mr-1">Table Controls:</span>
              <button
                onClick={() => editor.chain().focus().addRowBefore().run()}
                className="px-1.5 py-0.5 hover:bg-blue-100 rounded"
                title="Add Row Above"
              >
                +Row Above
              </button>
              <button
                onClick={() => editor.chain().focus().addRowAfter().run()}
                className="px-1.5 py-0.5 hover:bg-blue-100 rounded"
                title="Add Row Below"
              >
                +Row Below
              </button>
              <button
                onClick={() => editor.chain().focus().deleteRow().run()}
                className="px-1.5 py-0.5 hover:bg-red-100 text-red-700 rounded"
                title="Delete Row"
              >
                -Row
              </button>
              <div className="w-[1px] h-3 bg-blue-300 mx-1" />
              <button
                onClick={() => editor.chain().focus().addColumnBefore().run()}
                className="px-1.5 py-0.5 hover:bg-blue-100 rounded"
                title="Add Column Before"
              >
                +Col Left
              </button>
              <button
                onClick={() => editor.chain().focus().addColumnAfter().run()}
                className="px-1.5 py-0.5 hover:bg-blue-100 rounded"
                title="Add Column After"
              >
                +Col Right
              </button>
              <button
                onClick={() => editor.chain().focus().deleteColumn().run()}
                className="px-1.5 py-0.5 hover:bg-red-100 text-red-700 rounded"
                title="Delete Column"
              >
                -Col
              </button>
              <div className="w-[1px] h-3 bg-blue-300 mx-1" />
              <button
                onClick={() => editor.chain().focus().mergeCells().run()}
                disabled={!editor.can().mergeCells()}
                className="px-1.5 py-0.5 hover:bg-blue-100 rounded disabled:cursor-not-allowed disabled:opacity-40"
                title="Merge selected cells"
              >
                Merge
              </button>
              <button
                onClick={() => editor.chain().focus().splitCell().run()}
                disabled={!editor.can().splitCell()}
                className="px-1.5 py-0.5 hover:bg-blue-100 rounded disabled:cursor-not-allowed disabled:opacity-40"
                title="Split selected cell"
              >
                Split
              </button>
              <button
                onClick={() => editor.chain().focus().toggleHeaderRow().run()}
                className="px-1.5 py-0.5 hover:bg-blue-100 rounded"
                title="Toggle header row"
              >
                Header
              </button>
              <button
                onClick={() => {
                  const { $from } = editor.state.selection;
                  let tableDepth = $from.depth;
                  while (tableDepth > 0 && $from.node(tableDepth).type.name !== 'table') tableDepth -= 1;
                  if (tableDepth > 0) editor.chain().focus().setNodeSelection($from.before(tableDepth)).run();
                }}
                className="px-1.5 py-0.5 hover:bg-blue-100 rounded"
                title="Select whole table"
              >
                Select
              </button>
              <div className="w-[1px] h-3 bg-blue-300 mx-1" />
              <button
                onClick={() => editor.chain().focus().deleteTable().run()}
                className="px-1.5 py-0.5 hover:bg-red-200 bg-red-100 text-red-800 font-semibold rounded"
                title="Delete Table"
              >
                Delete Table
              </button>
            </div>
          )}
        </div>

        {/* Main Work Area: Desk view with A4 Page and Fields Sidebar */}
        <div className="flex-1 flex justify-center items-start gap-6 p-6 overflow-y-auto">
          {/* A4 Desk Page */}
          <div
            ref={canvasRef}
            className={`bg-white shadow-2xl rounded-xs min-h-[1050px] max-w-[800px] w-full p-12 border relative transition-colors ${dragOverCanvas ? 'border-indigo-500 ring-4 ring-indigo-100' : 'border-slate-300/70'}`}
            onDragOver={(event) => {
              if (event.dataTransfer.types.includes('application/x-clubdocs-block')) {
                event.preventDefault();
                event.dataTransfer.dropEffect = 'copy';
                setDragOverCanvas(true);
                const position = getDropPosition(editor, event);
                if (position !== null && editor) {
                  try {
                    const coords = editor.view.coordsAtPos(position);
                    const rect = canvasRef.current?.getBoundingClientRect();
                    if (rect) {
                      setDropIndicator({
                        top: Math.max(8, coords.top - rect.top),
                        left: 20,
                        width: Math.max(80, rect.width - 40),
                      });
                    }
                  } catch {
                    setDropIndicator(null);
                  }
                }
              }
            }}
            onDragLeave={(event) => {
              if (!event.currentTarget.contains(event.relatedTarget as Node)) {
                setDragOverCanvas(false);
                setDropIndicator(null);
              }
            }}
            onDragEnd={() => {
              setDragOverCanvas(false);
              setDropIndicator(null);
            }}
            onDrop={(event) => {
              const blockId = event.dataTransfer.getData('application/x-clubdocs-block');
              if (!blockId) return;
              event.preventDefault();
              insertDraggedBlock(blockId, getDropPosition(editor, event));
            }}
          >
            {dragOverCanvas && (
              <div className="absolute inset-x-12 top-4 z-10 rounded-lg border border-indigo-300 bg-indigo-50 px-3 py-2 text-center text-xs font-semibold text-indigo-800 shadow-sm">
                Drop to insert this document block at the pointer position
              </div>
            )}
            {dropIndicator && (
              <div
                className="template-editor-drop-indicator"
                style={{
                  top: `${dropIndicator.top}px`,
                  left: `${dropIndicator.left}px`,
                  width: `${dropIndicator.width}px`,
                }}
                aria-hidden="true"
              />
            )}
            {/* SVNIT Official Header Simulation */}
            <div className="border-b-2 border-slate-800 pb-4 mb-6 flex items-center justify-between">
              <div className="w-16 h-16 bg-slate-50 border border-slate-200 rounded flex items-center justify-center text-[10px] text-slate-400 font-mono">
                Club Logo
              </div>
              <div className="text-center flex-1 px-4">
                <h2 className="text-xs font-bold tracking-wider text-slate-800 uppercase">
                  Sardar Vallabhbhai National Institute of Technology, Surat
                </h2>
                <h3 className="text-[11px] font-semibold text-slate-600 uppercase mt-0.5">
                  Student Activity Council • Official Chapter Document
                </h3>
              </div>
              <div className="w-16 h-16 bg-slate-50 border border-slate-200 rounded flex items-center justify-center text-[10px] text-slate-400 font-mono">
                SVNIT Logo
              </div>
            </div>

            {/* TipTap Document Canvas */}
            <EditorContent editor={editor} className="prose prose-slate max-w-none focus:outline-none min-h-[600px]" />

            {/* Floating Selection Menu */}
            {bubblePos && editor && !editor.state.selection.empty && (
              <div
                style={{ top: `${bubblePos.top}px`, left: `${bubblePos.left}px` }}
                className="fixed z-50 bg-slate-900 text-white rounded-lg shadow-xl px-2 py-1.5 flex items-center gap-1 border border-slate-700 text-xs animate-in fade-in"
              >
                <button
                  onClick={() => editor.chain().focus().toggleBold().run()}
                  className={`p-1 rounded hover:bg-slate-800 ${editor.isActive('bold') ? 'bg-slate-700 text-blue-400' : ''}`}
                >
                  <BoldIcon className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={() => editor.chain().focus().toggleItalic().run()}
                  className={`p-1 rounded hover:bg-slate-800 ${editor.isActive('italic') ? 'bg-slate-700 text-blue-400' : ''}`}
                >
                  <ItalicIcon className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={() => editor.chain().focus().toggleUnderline().run()}
                  className={`p-1 rounded hover:bg-slate-800 ${editor.isActive('underline') ? 'bg-slate-700 text-blue-400' : ''}`}
                >
                  <UnderlineIcon className="w-3.5 h-3.5" />
                </button>
                <div className="w-[1px] h-4 bg-slate-700 mx-1" />
                <button
                  onClick={() => setShowAddFieldModal(true)}
                  className="px-2 py-1 rounded hover:bg-slate-800 flex items-center gap-1 text-indigo-300 font-medium"
                >
                  <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                  <span>Insert Field</span>
                </button>
              </div>
            )}

            {/* Slash Command Popup Menu */}
            {showSlashMenu && (
              <div className="absolute z-50 bg-white border border-slate-200 rounded-lg shadow-xl w-64 overflow-hidden left-12 top-48">
                <div className="px-3 py-1.5 bg-slate-50 border-b border-slate-100 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                  Insert Element (type /)
                </div>
                <div className="p-1 max-h-60 overflow-y-auto">
                  {slashOptions.map((opt, idx) => (
                    <button
                      key={opt.title}
                      onClick={() => {
                        opt.action();
                        setShowSlashMenu(false);
                      }}
                      className={`w-full flex items-center gap-2.5 px-3 py-2 text-left rounded-md transition ${
                        slashMenuIndex === idx ? 'bg-indigo-50 text-indigo-900' : 'hover:bg-slate-50 text-slate-700'
                      }`}
                    >
                      <div className="w-6 h-6 rounded bg-slate-100 flex items-center justify-center shrink-0">
                        {opt.icon}
                      </div>
                      <div>
                        <div className="text-xs font-semibold">{opt.title}</div>
                        <div className="text-[10px] text-slate-400">{opt.description}</div>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )}
            {/* Field Chip Settings Popover */}
            {chipPopover && (
              <div
                style={{ top: `${chipPopover.top}px`, left: `${chipPopover.left}px` }}
                className="fixed z-50 bg-white border border-slate-200 rounded-xl shadow-2xl p-4 w-80 text-xs animate-in fade-in"
              >
                <div className="flex items-center justify-between pb-2 border-b border-slate-100 mb-3">
                  <div className="flex items-center gap-1.5 font-bold text-slate-900 text-sm">
                    <span className="text-indigo-600">⚡</span>
                    <span>{chipPopover.label}</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => setChipPopover(null)}
                    className="text-slate-400 hover:text-slate-600 p-0.5 rounded cursor-pointer"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>

                <div className="space-y-2.5 text-slate-700">
                  <div>
                    <span className="font-semibold text-slate-500 uppercase text-[10px] tracking-wider block">
                      Field Key
                    </span>
                    <span className="font-mono text-slate-800 bg-slate-50 px-1.5 py-0.5 rounded border border-slate-200 text-[11px]">
                      {chipPopover.fieldName}
                    </span>
                  </div>

                  <div>
                    <span className="font-semibold text-slate-500 uppercase text-[10px] tracking-wider block">
                      Display label
                    </span>
                    <input
                      value={chipPopover.label}
                      onChange={(event) => handleUpdateChip({ label: event.target.value })}
                      className="mt-1 w-full rounded border border-slate-300 bg-white px-2 py-1.5 text-xs text-slate-800 focus:outline-indigo-500"
                      aria-label="Field display label"
                    />
                  </div>

                  <div>
                    <span className="font-semibold text-slate-500 uppercase text-[10px] tracking-wider block">
                      Field type
                    </span>
                    <select
                      value={chipPopover.fieldType}
                      onChange={(event) => handleUpdateChip({ fieldType: event.target.value })}
                      className="mt-1 w-full rounded border border-slate-300 bg-white px-2 py-1.5 text-xs text-slate-800 focus:outline-indigo-500"
                      aria-label="Field type"
                    >
                      <option value="text">Text</option>
                      <option value="longtext">Long text</option>
                      <option value="date">Date</option>
                      <option value="money">Money</option>
                      <option value="int">Integer</option>
                      <option value="enum">Dropdown</option>
                    </select>
                  </div>

                  <div>
                    <span className="font-semibold text-slate-500 uppercase text-[10px] tracking-wider block">
                      Ask / Prompt
                    </span>
                    <input
                      value={chipPopover.ask || ''}
                      onChange={(event) => handleUpdateChip({ ask: event.target.value })}
                      placeholder={`Please enter ${chipPopover.label}`}
                      className="mt-1 w-full rounded border border-slate-300 bg-white px-2 py-1.5 text-xs text-slate-800 focus:outline-indigo-500"
                      aria-label="Field prompt"
                    />
                  </div>

                  <div className="pt-2 border-t border-slate-100 space-y-3">
                    {/* Toggle: Required to create document */}
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <label htmlFor="popoverReqToggle" className="font-bold text-slate-800 cursor-pointer block">
                          Required to create document
                        </label>
                        <p className="text-[10px] text-slate-500 leading-tight mt-0.5">
                          Sets importance to essential. Users must fill this to generate document.
                        </p>
                      </div>
                      <input
                        type="checkbox"
                        id="popoverReqToggle"
                        checked={chipPopover.required}
                        onChange={(e) => handleToggleChipRequired(e.target.checked)}
                        className="mt-1 h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 cursor-pointer"
                      />
                    </div>

                    {/* Toggle: Sensitive */}
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <label
                          htmlFor="popoverSensToggle"
                          className="font-bold text-slate-800 cursor-pointer block flex items-center gap-1"
                        >
                          <span>Sensitive</span>
                          <span className="text-[10px] text-amber-600">🔒</span>
                        </label>
                        <p className="text-[10px] text-slate-500 leading-tight mt-0.5">
                          Sensitive fields (like bank details, PAN) are never visible to editors or unauthorized users.
                        </p>
                      </div>
                      <input
                        type="checkbox"
                        id="popoverSensToggle"
                        checked={chipPopover.sensitive}
                        onChange={(e) => handleToggleChipSensitive(e.target.checked)}
                        className="mt-1 h-4 w-4 rounded border-slate-300 text-amber-600 focus:ring-amber-500 cursor-pointer"
                      />
                    </div>
                  </div>

                  <div className="flex items-center justify-between gap-2 border-t border-slate-100 pt-3">
                    <span className="text-[10px] leading-tight text-slate-500">Changes apply to every chip using this field key.</span>
                    <button
                      type="button"
                      onClick={handleDeleteChip}
                      className="inline-flex shrink-0 items-center gap-1 rounded border border-rose-200 bg-rose-50 px-2 py-1 text-[10px] font-semibold text-rose-700 hover:bg-rose-100"
                    >
                      <Trash2 className="w-3 h-3" />
                      Remove chip
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Right Sidebar: Fields & Template Settings */}
          <aside className="w-80 bg-white rounded-lg border border-slate-200 shadow-sm p-4 flex flex-col gap-5 shrink-0 sticky top-[110px]">
            <div>
              <div className="flex items-center gap-1.5 mb-2">
                <Rows className="w-4 h-4 text-indigo-600" />
                <h3 className="font-bold text-sm text-slate-800">Drag blocks into the page</h3>
              </div>
              <div className="grid grid-cols-2 gap-2">
                {blockPalette.map((block) => (
                  <button
                    key={block.id}
                    type="button"
                    draggable
                    onDragStart={(event) => {
                      event.dataTransfer.setData('application/x-clubdocs-block', block.id);
                      event.dataTransfer.effectAllowed = 'copy';
                      setDragOverCanvas(false);
                      setDropIndicator(null);
                    }}
                    onClick={() => insertDraggedBlock(block.id)}
                    onDragEnd={() => {
                      setDragOverCanvas(false);
                      setDropIndicator(null);
                    }}
                    className="flex min-h-16 flex-col items-start gap-1 rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-2 text-left transition hover:border-indigo-300 hover:bg-indigo-50 active:cursor-grabbing"
                    title={`${block.description}. Click or drag to insert.`}
                  >
                    <GripVertical className="w-3 h-3 self-end text-slate-300" aria-hidden="true" />
                    {block.icon}
                    <span className="text-[11px] font-semibold text-slate-800">{block.label}</span>
                  </button>
                ))}
              </div>
              <p className="mt-2 text-[10px] leading-relaxed text-slate-400">Click a block to insert it, or drag it onto the page for a faster layout workflow.</p>
            </div>

            {selectedImageBlock && (
              <div className="template-editor-image-controls rounded-lg border border-sky-200 bg-sky-50/70 p-3">
                <div className="flex items-center justify-between gap-2 mb-2">
                  <div className="flex items-center gap-1.5">
                    <ImageIcon className="w-4 h-4 text-sky-700" />
                    <h3 className="font-bold text-sm text-sky-950">Image block</h3>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      editor?.chain().focus().setNodeSelection(selectedImageBlock.position).deleteSelection().run();
                      setSelectedImageBlock(null);
                      setSaveStatus('unsaved');
                      triggerAutosave();
                    }}
                    className="inline-flex items-center gap-1 rounded px-1.5 py-1 text-[10px] font-semibold text-rose-700 hover:bg-rose-100"
                    title="Remove selected image block"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    Remove
                  </button>
                </div>

                <label className="block text-[10px] font-semibold uppercase tracking-wide text-sky-800 mb-1">Block type</label>
                <select
                  value={selectedImageBlock.attrs.imageType || 'image'}
                  onChange={(event) => {
                    const imageType = event.target.value;
                    updateImageBlock({
                      imageType,
                      ...(imageType === 'club-logo'
                        ? { placeholderText: 'Choose a club logo from the asset library', alt: 'Club logo' }
                        : { placeholderText: 'Select an image to place here' }),
                    });
                  }}
                  className="w-full mb-2 rounded border border-sky-200 bg-white px-2 py-1.5 text-xs text-slate-800 focus:outline-sky-500"
                >
                  <option value="club-logo">Club logo</option>
                  <option value="image">Image</option>
                </select>

                {(selectedImageBlock.attrs.imageType === 'club-logo' || selectedImageBlock.attrs.imageType === 'logo') && (
                  <>
                    <label className="block text-[10px] font-semibold uppercase tracking-wide text-sky-800 mb-1">Club logo asset</label>
                    <select
                      value={selectedImageBlock.attrs.clubLogoAssetId || selectedImageBlock.attrs.logoAssetId || selectedImageBlock.attrs.assetId || ''}
                      onChange={(event) => selectClubLogo(event.target.value)}
                      className="w-full mb-2 rounded border border-sky-200 bg-white px-2 py-1.5 text-xs text-slate-800 focus:outline-sky-500"
                    >
                      <option value="">Choose a logo…</option>
                      {clubLogoOptions.map((option) => (
                        <option key={option.id} value={option.id}>{option.name}</option>
                      ))}
                    </select>
                    {clubLogoOptions.length === 0 && (
                      <p className="mb-2 rounded border border-dashed border-sky-300 bg-white/70 p-2 text-[10px] leading-relaxed text-sky-800">
                        No club logo assets are available yet. Upload one in Club Settings, or provide clubLogoOptions when embedding this editor.
                      </p>
                    )}
                  </>
                )}

                {selectedImageBlock.attrs.imageType !== 'club-logo' && selectedImageBlock.attrs.imageType !== 'logo' && (
                  <>
                    <label className="block text-[10px] font-semibold uppercase tracking-wide text-sky-800 mb-1">Image URL</label>
                    <input
                      value={selectedImageBlock.attrs.src || ''}
                      onChange={(event) => updateImageBlock({ src: event.target.value })}
                      placeholder="https://… (optional)"
                      className="w-full mb-2 rounded border border-sky-200 bg-white px-2 py-1.5 text-xs text-slate-800 focus:outline-sky-500"
                    />
                  </>
                )}

                <div className="grid grid-cols-2 gap-2">
                  <label className="block text-[10px] font-semibold uppercase tracking-wide text-sky-800">
                    Placement
                    <select
                      value={selectedImageBlock.attrs.placement || 'center'}
                      onChange={(event) => updateImageBlock({ placement: event.target.value })}
                      className="mt-1 w-full rounded border border-sky-200 bg-white px-2 py-1.5 text-xs font-normal text-slate-800 focus:outline-sky-500"
                    >
                      <option value="left">Left</option>
                      <option value="center">Center</option>
                      <option value="right">Right</option>
                    </select>
                  </label>
                  <label className="block text-[10px] font-semibold uppercase tracking-wide text-sky-800">
                    Height (px)
                    <input
                      type="number"
                      min={32}
                      max={800}
                      value={selectedImageBlock.attrs.height || 180}
                      onChange={(event) => updateImageBlock({ height: Math.max(32, Math.min(800, Number(event.target.value) || 180)) })}
                      className="mt-1 w-full rounded border border-sky-200 bg-white px-2 py-1.5 text-xs font-normal text-slate-800 focus:outline-sky-500"
                    />
                  </label>
                </div>

                <label className="block mt-2 text-[10px] font-semibold uppercase tracking-wide text-sky-800">
                  Alt text
                  <input
                    value={selectedImageBlock.attrs.alt || ''}
                    onChange={(event) => updateImageBlock({ alt: event.target.value })}
                    className="mt-1 w-full rounded border border-sky-200 bg-white px-2 py-1.5 text-xs font-normal text-slate-800 focus:outline-sky-500"
                  />
                </label>
                <label className="block mt-2 text-[10px] font-semibold uppercase tracking-wide text-sky-800">
                  Caption (optional)
                  <input
                    value={selectedImageBlock.attrs.caption || ''}
                    onChange={(event) => updateImageBlock({ caption: event.target.value })}
                    className="mt-1 w-full rounded border border-sky-200 bg-white px-2 py-1.5 text-xs font-normal text-slate-800 focus:outline-sky-500"
                  />
                </label>
              </div>
            )}

            <div>
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-1.5">
                  <Tag className="w-4 h-4 text-indigo-600" />
                  <h3 className="font-bold text-sm text-slate-800">Fields ({fields.length})</h3>
                </div>
                <button
                  onClick={() => setShowAddFieldModal(true)}
                  className="inline-flex items-center gap-1 px-2 py-1 text-xs font-semibold text-indigo-700 bg-indigo-50 hover:bg-indigo-100 rounded border border-indigo-200 transition"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Add Field</span>
                </button>
              </div>

              <div className="flex flex-col gap-2 max-h-[380px] overflow-y-auto pr-1">
                {fields.length === 0 ? (
                  <div className="p-4 border border-dashed border-slate-200 rounded text-center text-xs text-slate-400">
                    No fields defined yet. Click "Add Field" to create one.
                  </div>
                ) : (
                  fields.map(f => (
                    <div
                      key={f.key}
                      className="p-2.5 bg-slate-50 hover:bg-slate-100/80 rounded border border-slate-200 flex items-center justify-between group transition"
                    >
                      <div className="overflow-hidden">
                        <div className="flex items-center gap-1.5 truncate">
                          <span className="text-xs font-semibold text-slate-800 truncate">{f.label || f.key}</span>
                          <span
                            className={`text-[9px] px-1.5 py-0.2 rounded font-bold uppercase tracking-wider ${
                              f.importance === 'essential' || f.required
                                ? 'bg-rose-100 text-rose-700'
                                : 'bg-slate-200/70 text-slate-600'
                            }`}
                          >
                            {f.importance === 'essential' || f.required ? 'Essential' : 'Optional'}
                          </span>
                          {f.sensitive && (
                            <span
                              className="text-[9px] px-1 py-0.2 rounded font-bold uppercase tracking-wider bg-amber-100 text-amber-800"
                              title="Sensitive field"
                            >
                              🔒
                            </span>
                          )}
                        </div>
                        <div className="text-[11px] font-mono text-slate-500 truncate mt-0.5">
                          {`{{ ${f.key} }}`} • <span className="text-indigo-600">{f.type}</span>
                        </div>
                      </div>
                      <button
                        onClick={() =>
                          insertFieldChip(
                            editor,
                            f.key,
                            f.label,
                            f.type,
                            f.ask,
                            f.importance || (f.required ? 'essential' : 'optional'),
                            f.required,
                            f.sensitive
                          )
                        }
                        className="px-2 py-1 bg-white hover:bg-indigo-50 border border-slate-200 hover:border-indigo-300 rounded text-xs font-semibold text-indigo-600 shadow-2xs transition shrink-0 ml-2 cursor-pointer"
                        title="Insert chip at cursor"
                      >
                        Insert
                      </button>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Letterhead configuration */}
            <div className="border-t border-slate-200 pt-4">
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                Official Letterhead
              </label>
              <select
                value={selectedLetterheadId}
                onChange={e => {
                  setSelectedLetterheadId(e.target.value);
                  setSaveStatus('unsaved');
                  triggerAutosave();
                }}
                className="w-full text-xs border border-slate-300 rounded px-2.5 py-1.5 bg-white text-slate-800 focus:outline-indigo-500"
              >
                <option value="">Default SVNIT Header</option>
                {letterheads.map(lh => (
                  <option key={lh.id} value={lh.id}>
                    {lh.name}
                  </option>
                ))}
              </select>
            </div>
          </aside>

          {/* Isolated assistant integration slot. A host can provide a real
              chat panel without making the editor depend on that component. */}
          <aside className="template-editor-assistant w-80 shrink-0 self-start sticky top-[110px] overflow-hidden rounded-xl border border-indigo-200 bg-white shadow-sm">
            <div className="flex items-center gap-2 border-b border-indigo-100 bg-indigo-50 px-4 py-3">
              <Bot className="w-4 h-4 text-indigo-700" />
              <div>
                <h3 className="text-sm font-bold text-indigo-950">Assistant</h3>
                <p className="text-[10px] text-indigo-700">Draft guidance and document help</p>
              </div>
            </div>
            <div className="min-h-[180px] p-3">
              {assistantContent || (
                <div className="flex min-h-[150px] flex-col items-center justify-center rounded-lg border border-dashed border-indigo-200 bg-indigo-50/40 px-4 py-6 text-center">
                  <Bot className="mb-2 h-7 w-7 text-indigo-300" />
                  <p className="text-xs font-semibold text-indigo-900">Assistant slot ready</p>
                  <p className="mt-1 text-[10px] leading-relaxed text-slate-500">
                    Connect a chat panel through the <code className="rounded bg-white px-1">assistantSlot</code> prop.
                  </p>
                </div>
              )}
            </div>
          </aside>
        </div>

        {/* Modal: Add Custom Field */}
        {showAddFieldModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs">
            <div className="bg-white rounded-lg shadow-xl w-full max-w-md p-6 border border-slate-200">
              <div className="flex items-center justify-between pb-3 border-b border-slate-100 mb-4">
                <h3 className="font-bold text-base text-slate-900">Add Document Field</h3>
                <button
                  onClick={() => setShowAddFieldModal(false)}
                  className="text-slate-400 hover:text-slate-600"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <form onSubmit={handleAddField} className="flex flex-col gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Field Label / Name</label>
                  <input
                    type="text"
                    required
                    value={newFieldName}
                    onChange={e => setNewFieldName(e.target.value)}
                    placeholder="e.g. Chief Guest Name, Event Date"
                    className="w-full text-sm border border-slate-300 rounded-md px-3 py-2 text-slate-900 focus:outline-indigo-500"
                  />
                  {newFieldName && (
                    <div className="text-[11px] font-mono text-slate-400 mt-1">
                      Key: {newFieldName.trim().toLowerCase().replace(/[^a-z0-9_]/g, '_')}
                    </div>
                  )}
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Field Type</label>
                  <select
                    value={newFieldType}
                    onChange={e => setNewFieldType(e.target.value)}
                    className="w-full text-sm border border-slate-300 rounded-md px-3 py-2 bg-white text-slate-800 focus:outline-indigo-500"
                  >
                    <option value="text">Text (Single line)</option>
                    <option value="longtext">Long Text (Paragraphs)</option>
                    <option value="date">Date</option>
                    <option value="money">Money (INR ₹)</option>
                    <option value="int">Integer count</option>
                    <option value="enum">Dropdown (Enum)</option>
                  </select>
                </div>

                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="fieldReq"
                    checked={newFieldRequired}
                    onChange={e => setNewFieldRequired(e.target.checked)}
                    className="rounded border-slate-300 text-indigo-600"
                  />
                  <label htmlFor="fieldReq" className="text-xs text-slate-700 font-medium">
                    Required when generating documents
                  </label>
                </div>

                <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100">
                  <button
                    type="button"
                    onClick={() => setShowAddFieldModal(false)}
                    className="px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 rounded-md"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-md shadow-xs"
                  >
                    Add & Insert
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Modal: Live Preview */}
        {showPreviewModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-6">
            <div className="bg-white rounded-lg shadow-2xl max-w-4xl w-full max-h-[90vh] flex flex-col overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Eye className="w-5 h-5 text-indigo-600" />
                  <h3 className="font-bold text-slate-800 text-base">Template Live Preview</h3>
                  <span className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded font-mono">
                    Dummy Data Render
                  </span>
                </div>
                <button
                  onClick={() => setShowPreviewModal(false)}
                  className="text-slate-400 hover:text-slate-600"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="flex-1 overflow-y-auto p-6 bg-slate-100 flex flex-col items-center gap-6">
                {previewLoading ? (
                  <div className="flex flex-col items-center py-20 text-slate-500">
                    <RefreshCw className="w-8 h-8 animate-spin text-indigo-600 mb-3" />
                    <p className="text-sm">Generating PDF preview via LibreOffice...</p>
                  </div>
                ) : previewPages.length === 0 ? (
                  <div className="p-8 text-center text-slate-500">No preview generated.</div>
                ) : (
                  previewPages.map((pageSrc, idx) => (
                    <div key={idx} className="bg-white shadow-lg border border-slate-300 rounded overflow-hidden max-w-[700px] w-full">
                      <img src={pageSrc} alt={`Page ${idx + 1}`} className="w-full h-auto" />
                    </div>
                  ))
                )}
              </div>

              <div className="px-6 py-3 border-t border-slate-200 flex items-center justify-end">
                <button
                  onClick={() => setShowPreviewModal(false)}
                  className="px-4 py-2 text-sm font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-md"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Modal: Validation Report */}
        {showValidationModal && validationReport && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-xs p-6">
            <div className="bg-white rounded-lg shadow-xl max-w-xl w-full p-6">
              <div className="flex items-center justify-between pb-3 border-b border-slate-200 mb-4">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                  <h3 className="font-bold text-slate-800 text-base">Compiler Validation Report</h3>
                </div>
                <button
                  onClick={() => setShowValidationModal(false)}
                  className="text-slate-400 hover:text-slate-600"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="text-xs text-slate-600 flex flex-col gap-3 max-h-96 overflow-y-auto">
                <div className="p-3 bg-emerald-50 text-emerald-800 rounded border border-emerald-200 font-medium">
                  Document successfully compiled to python-docx and verified via SandboxedEnvironment.
                </div>
                <div>
                  <span className="font-semibold text-slate-700">Tags Extracted: </span>
                  <span className="font-mono">{validationReport.extracted_tags?.join(', ') || 'None'}</span>
                </div>
              </div>

              <div className="mt-6 flex justify-end">
                <button
                  onClick={() => setShowValidationModal(false)}
                  className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-md shadow-xs"
                >
                  OK
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Modal: Unreviewed AI Warning */}
        {unreviewedModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-6">
            <div className="bg-white rounded-lg shadow-xl max-w-lg w-full p-6 border border-amber-200">
              <div className="flex items-center gap-3 mb-4 text-amber-700">
                <AlertCircle className="w-6 h-6 text-amber-600 shrink-0" />
                <h3 className="font-bold text-base">Unreviewed AI Content</h3>
              </div>
              <p className="text-sm text-slate-600 mb-4">
                This template contains AI-suggested content or placeholders requiring official review before publication.
              </p>
              <div className="p-3 bg-amber-50 rounded border border-amber-200 text-xs text-amber-900 mb-6 max-h-48 overflow-y-auto">
                {unreviewedModal.map((item, idx) => (
                  <div key={idx} className="py-1">
                    • {item.description || item.label || 'Unreviewed block'}
                  </div>
                ))}
              </div>
              <div className="flex items-center justify-end gap-3">
                <button
                  onClick={() => setUnreviewedModal(null)}
                  className="px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 rounded-md"
                >
                  Review In Editor
                </button>
                <button
                  onClick={handleReviewAll}
                  disabled={reviewingAi}
                  className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-md shadow-xs"
                >
                  {reviewingAi ? 'Reviewing...' : 'Approve & Mark All Reviewed'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </EditorErrorBoundary>
  );
};
