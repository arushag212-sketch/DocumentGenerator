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
import { DEFAULT_DESIGN_SETTINGS, THEMES } from './themes';
import { TemplateField } from './FieldsPanel';
import { applyChatAction } from './applyChatAction';

// Replace the document and leave a collapsed cursor at the start. setContent can
// leave the whole document selected, and any later insert or rewrite would then
// replace every block.
function loadEditorContent(editor: any, content: any) {
  editor.chain().setContent(content).setTextSelection(1).run();
}

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
  const [clubLogoOptions, setClubLogoOptions] = useState<ClubLogoOption[]>(providedClubLogoOptions || []);
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

  const [designSettings, setDesignSettings] = useState<DesignSettings>(DEFAULT_DESIGN_SETTINGS);

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

  const [translating, setTranslating] = useState(false);

  const {
    editor,
    bubblePos,
    showSlashMenu,
    setShowSlashMenu,
    chipPopover,
    setChipPopover,
    selectedImageBlock,
    updateChip,
    toggleChipRequired,
    toggleChipSensitive,
    deleteChip,
    updateImageBlock,
  } = useTemplateEditor({
    onDocChange: () => markUnsaved(),
    clubId,
  });

  useEffect(() => {
    if (editor) {
      (window as any).editorInstance = editor;
    }
  }, [editor]);

  // Autosave
  const { saveStatus, conflictMessage, markUnsaved, saveNow } = useEditorAutosave({
    clubId,
    templateId,
    template,
    editor,
    designSettings,
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
          loadEditorContent(editor, migrateTipTapContent(draftData.editor_json));
          contentLoadedRef.current = true;
        }
        if (clubId && (!providedClubLogoOptions || providedClubLogoOptions.length === 0)) {
          api.clubs
            .getAssets(clubId)
            .then((assets) => {
              if (isMounted && Array.isArray(assets)) {
                setClubLogoOptions(
                  assets.map((a: any) => ({
                    id: a.id,
                    name: a.filename || 'Logo',
                    url: a.url || `/api/v1/assets/${a.id}/content`,
                    kind: a.kind || 'logo',
                  }))
                );
              }
            })
            .catch(() => {});
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
      loadEditorContent(editor, migrateTipTapContent(template.editor_json));
      contentLoadedRef.current = true;
    }
  }, [editor, template]);

  // AI Chat Copilot action applicator
  const handleApplyChatAction = useCallback(
    (action: any) => {
      applyChatAction({
        action,
        editor,
        setTemplate,
        setFields,
        setDesignSettings,
        markUnsaved,
      });
    },
    [editor, markUnsaved, setTemplate, setFields, setDesignSettings]
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
        design_settings: designSettings,
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

  const handleTranslate = async (targetLang: 'hi' | 'gu') => {
    if (!editor || !template) return;
    setTranslating(true);
    try {
      const res = await api.documents.translateTemplate(clubId, templateId, {
        target_lang: targetLang,
        editor_json: editor.getJSON(),
      });
      if (res?.editor_json) {
        loadEditorContent(editor, res.editor_json);
        if (res.design_settings?.fontFamily) {
          setDesignSettings((prev) => ({
            ...prev,
            fontFamily: res.design_settings.fontFamily,
            headingFontFamily: res.design_settings.headingFontFamily || res.design_settings.fontFamily,
          }));
        }
        markUnsaved();
      }
    } catch (err: any) {
      alert(err.message || 'Translation failed');
    } finally {
      setTranslating(false);
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
        onTranslate={handleTranslate}
        translating={translating}
      />

      <div className="flex flex-1 overflow-hidden relative">
        <EditorErrorBoundary title="Palette Error">
          <PalettePanel
            editor={editor}
            isOpen={leftOpen}
            onToggle={() => setLeftOpen(!leftOpen)}
            clubLogoOptions={clubLogoOptions}
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
            onUpdateChip={updateChip}
            onToggleChipRequired={toggleChipRequired}
            onToggleChipSensitive={toggleChipSensitive}
            onDeleteChip={deleteChip}
            selectedImageBlock={selectedImageBlock}
            onUpdateImageBlock={updateImageBlock}
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
            const svnit = THEMES.find((t) => t.id === 'svnit_gold');
            if (svnit) {
              setDesignSettings((prev) => ({
                ...prev,
                theme: svnit.id,
                headingColor: svnit.heading_color,
                textColor: svnit.text_color,
                tableHeaderBg: svnit.table_header_bg,
                tableHeaderTextColor: svnit.table_header_text,
                borderColor: svnit.border_color,
                dividerColor: svnit.divider_color,
                fontFamily: svnit.body_font,
                headingFontFamily: svnit.heading_font,
                pageBorder: svnit.border_style,
                pageBg: svnit.page_bg,
              }));
              markUnsaved();
            }
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
