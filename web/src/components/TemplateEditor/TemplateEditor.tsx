import React, { useState, useEffect, useRef, useCallback } from 'react';
import { api } from '../../api/client';
import { migrateTipTapContent } from './extensions';
import { EditorErrorBoundary } from './EditorErrorBoundary';
import { Toolbar } from './Toolbar';
import { PalettePanel } from './PalettePanel';
import { Canvas } from './Canvas';
import { RightTabsPanel } from './RightTabsPanel';
import { useTemplateEditor } from './useTemplateEditor';
import { useEditorAutosave } from './useEditorAutosave';
import { ShortcutsModal } from './ShortcutsModal';
import { FindReplaceModal } from './FindReplaceModal';
import { PreviewModal, ValidationModal, UnreviewedAiModal } from './TemplateEditorModals';
import { DesignSettings } from './DesignPanel';
import { TemplateField } from './FieldsPanel';

export interface ClubLogoOption {
  id: string;
  name: string;
  url: string;
  alt?: string;
  kind?: string;
}

interface TemplateEditorProps {
  clubId: string;
  templateId: string;
  onBack: () => void;
  assistantSlot?: React.ReactNode;
  clubLogoOptions?: ClubLogoOption[];
}

export const TemplateEditor: React.FC<TemplateEditorProps> = ({
  clubId,
  templateId,
  onBack,
  clubLogoOptions: providedClubLogoOptions,
}) => {
  const [template, setTemplate] = useState<any>(null);
  const [fields, setFields] = useState<TemplateField[]>([]);
  const [clubLogoOptions] = useState<ClubLogoOption[]>(providedClubLogoOptions || []);
  const [loading, setLoading] = useState(true);
  const [zoom, setZoom] = useState(1);

  // Panel collapse states
  const [leftOpen, setLeftOpen] = useState(true);
  const [rightOpen, setRightOpen] = useState(true);
  const [isMobile, setIsMobile] = useState(false);

  // Modals
  const [showShortcuts, setShowShortcuts] = useState(false);
  const [showFindReplace, setShowFindReplace] = useState(false);
  const [showPreviewModal, setShowPreviewModal] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewPages, setPreviewPages] = useState<string[]>([]);
  const [validationReport] = useState<any>(null);
  const [showValidationModal, setShowValidationModal] = useState(false);
  const [unreviewedModal, setUnreviewedModal] = useState<any[] | null>(null);
  const [reviewingAi, setReviewingAi] = useState(false);

  const [designSettings, setDesignSettings] = useState<DesignSettings>({
    theme: 'official_navy',
    fontFamily: 'serif',
    fontSize: 'base',
    lineHeight: 'normal',
    orientation: 'portrait',
    margins: 'normal',
    watermark: '',
  });

  const contentLoadedRef = useRef<boolean>(false);

  // Responsive breakpoint detector
  useEffect(() => {
    const handleResize = () => {
      const width = window.innerWidth;
      setIsMobile(width < 768);
      if (width < 1024) setLeftOpen(false);
    };
    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // TipTap editor with interactions
  const {
    editor,
    bubblePos,
    showSlashMenu,
    setShowSlashMenu,
    chipPopover,
    setChipPopover,
    selectedImageBlock,
  } = useTemplateEditor({
    onDocChange: () => markUnsaved(),
  });

  // Autosave
  const { saveStatus, conflictMessage, markUnsaved, saveNow } = useEditorAutosave({
    clubId,
    templateId,
    template,
    editor,
    onSaveSuccess: (updated) => setTemplate(updated),
  });

  // Fetch template draft data
  useEffect(() => {
    let isMounted = true;
    const fetchDraft = async () => {
      setLoading(true);
      try {
        const draftData = await api.documents.getTemplateDraft(clubId, templateId);
        if (!isMounted) return;

        setTemplate(draftData);
        setFields(draftData.fields || []);
        if (draftData.design_settings) {
          setDesignSettings((prev) => ({ ...prev, ...draftData.design_settings }));
        }

        if (editor && draftData.editor_json && !contentLoadedRef.current) {
          editor.commands.setContent(migrateTipTapContent(draftData.editor_json));
          contentLoadedRef.current = true;
        }
      } catch (err: any) {
        console.error('Failed to load template:', err);
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    fetchDraft();
    return () => {
      isMounted = false;
    };
  }, [clubId, templateId, editor]);

  // Sync content once if editor initialized after template fetch
  useEffect(() => {
    if (editor && template?.editor_json && !contentLoadedRef.current) {
      editor.commands.setContent(migrateTipTapContent(template.editor_json));
      contentLoadedRef.current = true;
    }
  }, [editor, template]);

  // AI Chat Copilot action applicator
  const handleApplyChatAction = useCallback(
    (action: any) => {
      if (!editor) return;
      if (action.type === 'set_title') {
        setTemplate((prev: any) => ({ ...prev, name: action.payload?.title || action.title }));
        markUnsaved();
      } else if (action.type === 'insert_block' && action.payload?.block) {
        editor.chain().focus().insertContent(action.payload.block).run();
        markUnsaved();
      } else if (action.type === 'add_field' && action.payload?.field) {
        setFields((prev) => [...prev, action.payload.field]);
        markUnsaved();
      }
    },
    [editor, markUnsaved]
  );

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
        fields,
      });
      setPreviewPages(res.pages || []);
    } catch (err: any) {
      alert(err.message || 'Preview generation failed');
      setShowPreviewModal(false);
    } finally {
      setPreviewLoading(false);
    }
  };

  const handlePublish = async () => {
    if (!editor || !template) return;
    await saveNow();
    try {
      const res = await api.documents.publishTemplate(clubId, templateId);
      setTemplate((prev: any) => ({ ...prev, status: 'published' }));
      alert(`Template "${res.name}" published successfully!`);
    } catch (err: any) {
      if (err.status === 409 && err.detail?.unreviewed_items) {
        setUnreviewedModal(err.detail.unreviewed_items);
      } else {
        alert(err.message || 'Publishing failed');
      }
    }
  };

  const handleApproveAllAi = async () => {
    setReviewingAi(true);
    try {
      await api.documents.reviewAiTemplate(clubId, templateId, { all: true });
      setUnreviewedModal(null);
      await saveNow();
    } catch (err: any) {
      alert(err.message || 'Failed to approve AI content');
    } finally {
      setReviewingAi(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="text-center">
          <div className="w-8 h-8 border-3 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
          <p className="text-xs text-slate-500 font-medium">Loading Template Studio…</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-slate-100 text-slate-900 font-sans">
      <Toolbar
        templateName={template?.name}
        category={template?.category}
        version={template?.version}
        saveStatus={saveStatus}
        conflictMessage={conflictMessage}
        onBack={onBack}
        editor={editor}
        zoom={zoom}
        onZoomChange={setZoom}
        onOpenFindReplace={() => setShowFindReplace(true)}
        onOpenShortcuts={() => setShowShortcuts(true)}
        onPreview={handlePreview}
        onPublish={handlePublish}
        previewLoading={previewLoading}
      />

      <div className="flex flex-1 overflow-hidden relative">
        <EditorErrorBoundary title="Palette Error">
          <PalettePanel
            editor={editor}
            isOpen={leftOpen}
            onToggle={() => setLeftOpen(!leftOpen)}
          />
        </EditorErrorBoundary>

        <EditorErrorBoundary title="Canvas Editor Error">
          <Canvas
            editor={editor}
            zoom={zoom}
            watermarkText={designSettings.watermark}
            orientation={designSettings.orientation}
            margins={designSettings.margins}
            bubblePos={bubblePos}
            chipPopover={chipPopover}
            onCloseChipPopover={() => setChipPopover(null)}
            onUpdateChip={(updates) => {
              if (!chipPopover || !editor) return;
              editor.commands.command(({ tr }: any) => {
                tr.setNodeMarkup(chipPopover.position, undefined, updates);
                return true;
              });
              markUnsaved();
            }}
            onToggleChipRequired={(req) => {
              if (!chipPopover || !editor) return;
              const imp = req ? 'essential' : 'optional';
              editor.commands.command(({ tr }: any) => {
                tr.setNodeMarkup(chipPopover.position, undefined, {
                  importance: imp,
                  required: req,
                });
                return true;
              });
              setChipPopover((prev: any) => ({ ...prev, required: req, importance: imp }));
              markUnsaved();
            }}
            onToggleChipSensitive={(sens) => {
              if (!chipPopover || !editor) return;
              editor.commands.command(({ tr }: any) => {
                tr.setNodeMarkup(chipPopover.position, undefined, { sensitive: sens });
                return true;
              });
              setChipPopover((prev: any) => ({ ...prev, sensitive: sens }));
              markUnsaved();
            }}
            onDeleteChip={() => {
              if (!chipPopover || !editor) return;
              editor.chain().focus().setNodeSelection(chipPopover.position).deleteSelection().run();
              setChipPopover(null);
              markUnsaved();
            }}
            selectedImageBlock={selectedImageBlock}
            onUpdateImageBlock={(updates) => {
              if (!selectedImageBlock || !editor) return;
              editor.chain().focus().setNodeSelection(selectedImageBlock.position).updateAttributes('imageBlock', updates).run();
              markUnsaved();
            }}
            clubLogoOptions={clubLogoOptions}
            showSlashMenu={showSlashMenu}
            onCloseSlashMenu={() => setShowSlashMenu(false)}
            onOpenAddField={() => setRightOpen(true)}
          />
        </EditorErrorBoundary>

        <RightTabsPanel
          clubId={clubId}
          templateId={templateId}
          editor={editor}
          fields={fields}
          onAddField={(newField) => {
            setFields((prev) => [...prev, newField]);
            markUnsaved();
          }}
          designSettings={designSettings}
          onDesignChange={(updates) => {
            setDesignSettings((prev) => ({ ...prev, ...updates }));
            markUnsaved();
          }}
          onAutoStyle={() => {
            setDesignSettings({
              theme: 'svnit_gold',
              fontFamily: 'serif',
              fontSize: 'base',
              lineHeight: 'normal',
              orientation: 'portrait',
              margins: 'normal',
              watermark: '',
            });
            markUnsaved();
          }}
          onApplyChatAction={handleApplyChatAction}
          isOpen={rightOpen}
          onToggle={() => setRightOpen(!rightOpen)}
          isMobile={isMobile}
        />
      </div>

      <ShortcutsModal isOpen={showShortcuts} onClose={() => setShowShortcuts(false)} />
      <FindReplaceModal isOpen={showFindReplace} onClose={() => setShowFindReplace(false)} editor={editor} />
      <PreviewModal isOpen={showPreviewModal} onClose={() => setShowPreviewModal(false)} loading={previewLoading} pages={previewPages} />
      <ValidationModal isOpen={showValidationModal} onClose={() => setShowValidationModal(false)} report={validationReport} />
      <UnreviewedAiModal items={unreviewedModal} onClose={() => setUnreviewedModal(null)} onApproveAll={handleApproveAllAi} reviewing={reviewingAi} />
    </div>
  );
};
