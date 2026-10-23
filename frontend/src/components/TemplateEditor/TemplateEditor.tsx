import React, { useState, useEffect, useRef, useCallback } from 'react';
import { api } from '../../api/client';
import { migrateTipTapContent } from './extensions';
import { EditorErrorBoundary } from './EditorErrorBoundary';
import { Plus, Tag, Palette, Sparkles } from 'lucide-react';
import { Toolbar } from './Toolbar';
import { PalettePanel, type LeftSidebarTab } from './PalettePanel';
import { Canvas } from './Canvas';
import { RightTabsPanel, type RightTabType } from './RightTabsPanel';
import { useTemplateEditor } from './useTemplateEditor';
import { useEditorAutosave } from './useEditorAutosave';
import { ShortcutsModal } from './ShortcutsModal';
import { FindReplaceModal } from './FindReplaceModal';
import { PreviewModal, ValidationModal, UnreviewedAiModal } from './TemplateEditorModals';
import { EditorTips } from './EditorTips';
import { DesignSettings } from './DesignPanel';
import { DEFAULT_DESIGN_SETTINGS, THEMES } from './themes';
import { TemplateField } from './FieldsPanel';
import { applyChatAction, type ApplyResult } from './applyChatAction';

// Replace the document and leave a collapsed cursor at the start. setContent can
// leave the whole document selected, and any later insert or rewrite would then
// replace every block.
// Loading saved content is not an edit: without emitUpdate: false TipTap 3 fires onUpdate, which
// marked every freshly opened template "Unsaved" (and triggered the leave-page warning).
function loadEditorContent(editor: any, content: any) {
  editor.chain().setContent(content, { emitUpdate: false }).setTextSelection(1).run();
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
  /** Opens the generate page for this template (shown once it is published). */
  onCreateDocument?: () => void;
  assistantSlot?: React.ReactNode;
  clubLogoOptions?: ClubLogoOption[];
}

export const TemplateEditor: React.FC<TemplateEditorProps> = ({
  clubId,
  templateId,
  onBack,
  onCreateDocument,
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
  const [leftTab, setLeftTab] = useState<LeftSidebarTab>('blocks');
  const [rightTab, setRightTab] = useState<RightTabType>('chat');
  // Below desktop width the panels open as sheets over the page, one at a time
  const isCompact = () => window.innerWidth < 1024;
  const openLeft = (tab: LeftSidebarTab) => {
    // With no cursor placed yet (usual on phones), new blocks go to the end, not above the title
    if (tab === 'blocks' && editor && !editor.isFocused && editor.state.selection.from <= 1) {
      editor.commands.setTextSelection(editor.state.doc.content.size);
    }
    setLeftTab(tab);
    setLeftOpen(true);
    if (isCompact()) setRightOpen(false);
  };
  const openRight = (tab: RightTabType) => {
    setRightTab(tab);
    setRightOpen(true);
    if (isCompact()) setLeftOpen(false);
  };

  // Modals
  const [showShortcuts, setShowShortcuts] = useState(false);
  const [showFindReplace, setShowFindReplace] = useState(false);
  const [showPreviewModal, setShowPreviewModal] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewPages, setPreviewPages] = useState<string[]>([]);
  const [validationReport] = useState<any>(null);
  const [showValidationModal, setShowValidationModal] = useState(false);
  const [unreviewedModal, setUnreviewedModal] = useState<any[] | null>(null);
  const [unreviewedAiCount, setUnreviewedAiCount] = useState(0);
  const [notice, setNotice] = useState<{ tone: 'success' | 'error'; text: string } | null>(null);

  // In-app toast dispatcher helper
  const showToast = useCallback((text: string, tone: 'success' | 'error' = 'success') => {
    setNotice({ tone, text });
  }, []);

  // Listen for custom toast events from child components (e.g. ImageBlockView, blockDragDrop)
  useEffect(() => {
    const handleToastEvent = (e: any) => {
      if (e.detail?.text) {
        setNotice({ tone: e.detail.tone === 'error' ? 'error' : 'success', text: e.detail.text });
      }
    };
    window.addEventListener('clubdocs-toast', handleToastEvent);
    return () => window.removeEventListener('clubdocs-toast', handleToastEvent);
  }, []);

  // Letterhead and footer exactly as generated documents print them
  const [clubFooter, setClubFooter] = useState('');
  // Example values typed in the Fields sidebar, used only by Preview
  const [sampleValues, setSampleValues] = useState<Record<string, string>>({});
  const [bannerFailed, setBannerFailed] = useState(false);

  useEffect(() => {
    let alive = true;
    api.clubs
      .get(clubId)
      .then((club: any) => {
        if (alive) setClubFooter((club?.settings?.footer_text || club?.name || '').trim());
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [clubId]);

  const letterhead = {
    header: bannerFailed ? (
      <div className="w-full h-14 rounded border-2 border-dashed border-slate-200 bg-slate-50 flex items-center justify-center text-xs text-slate-400 font-medium">
        SVNIT Club Letterhead (Configure in Club Settings)
      </div>
    ) : (
      <img
        src={`/api/v1/clubs/${clubId}/letterhead-banner`}
        alt="Club letterhead"
        className="w-full h-auto block rounded-xs shadow-2xs"
        draggable={false}
        onError={() => setBannerFailed(true)}
      />
    ),
    footer: (
      <p className="text-[11px] text-slate-500 border-t border-slate-200 pt-1.5" style={{ fontFamily: 'inherit' }}>
        {clubFooter ? `${clubFooter}  ·  ` : ''}Page 1 of 1
      </p>
    ),
  };

  useEffect(() => {
    if (!notice) return;
    const t = setTimeout(() => setNotice(null), 5000);
    return () => clearTimeout(t);
  }, [notice]);

  const [reviewingAi, setReviewingAi] = useState(false);
  const [designSettings, setDesignSettings] = useState<DesignSettings>(DEFAULT_DESIGN_SETTINGS);
  const contentLoadedRef = useRef<boolean>(false);

  // Responsive breakpoint detector
  useEffect(() => {
    const handleResize = () => {
      const width = window.innerWidth;
      // Phones and tablets: the right panel opens as a sheet over the page instead of squeezing it
      setIsMobile(width < 1024);
      if (width < 1024) setLeftOpen(false);
      // Below desktop width the side panels would squeeze the page to a sliver.
      if (width < 1280) setRightOpen(false);
    };
    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const [translating, setTranslating] = useState(false);

  // Fit the page to the space between the panels until the user picks a zoom.
  const userZoomRef = useRef(false);
  const handleZoomChange = (z: number) => {
    userZoomRef.current = true;
    setZoom(z);
  };
  useEffect(() => {
    const fit = () => {
      if (userZoomRef.current) return;
      const isDesktop = window.innerWidth >= 1024;
      const isWide = window.innerWidth >= 1280;
      const pageWidth = designSettings.orientation === 'landscape' ? 1123 : 794;
      const side = (leftOpen && isDesktop ? 288 : (isDesktop ? 48 : 0)) + (rightOpen && isWide ? 360 : (isDesktop && !isMobile ? 48 : 0));
      const available = window.innerWidth - side - (isDesktop ? 48 : 24);
      const next = Math.max(0.3, Math.min(1, Math.floor((available / pageWidth) * 20) / 20));
      setZoom(next);
    };
    fit();
    window.addEventListener('resize', fit);
    return () => window.removeEventListener('resize', fit);
  }, [designSettings.orientation, leftOpen, rightOpen, isMobile]);

  const {
    editor,
    bubblePos,
    showSlashMenu,
    setShowSlashMenu,
    inlinePicker,
    setInlinePicker,
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

  // Autosave
  const { saveStatus, conflictMessage, markUnsaved, saveNow } = useEditorAutosave({
    clubId,
    templateId,
    template,
    editor,
    designSettings,
    fields,
    onSaveSuccess: (updated) => setTemplate(updated),
  });

  // Warn before leaving with unsaved changes
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (saveStatus === 'unsaved') {
        e.preventDefault();
        e.returnValue = '';
      }
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [saveStatus]);

  const handleBackSafe = () => {
    if (saveStatus === 'unsaved') {
      const confirmLeave = window.confirm('You have unsaved changes in this template. Are you sure you want to leave?');
      if (!confirmLeave) return;
    }
    onBack();
  };

  // Global Keyboard Shortcuts (Ctrl+S, Ctrl+P, Esc). Preview goes through a ref so the shortcut
  // always uses the current fields and sample values, not the ones from the first render.
  const previewRef = useRef<() => void>(() => {});
  useEffect(() => {
    const handleGlobalKeyDown = (e: KeyboardEvent) => {
      // Ctrl+S / Cmd+S
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
        e.preventDefault();
        saveNow().then((ok) =>
          ok ? showToast('Template saved.', 'success') : showToast('Could not save the template. Please try again.', 'error'),
        );
      }
      // Ctrl+P / Cmd+P
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'p') {
        e.preventDefault();
        previewRef.current();
      }
      // Esc closes popovers / modals
      if (e.key === 'Escape') {
        setShowShortcuts(false);
        setShowFindReplace(false);
        setShowPreviewModal(false);
        setShowValidationModal(false);
        setUnreviewedModal(null);
        setChipPopover(null);
        setInlinePicker(null);
      }
    };

    window.addEventListener('keydown', handleGlobalKeyDown);
    return () => window.removeEventListener('keydown', handleGlobalKeyDown);
  }, [saveNow, showToast]);

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

  // Keep a snapshot before each applied action so onUndo can restore it cleanly
  const chatSnapshotsRef = useRef<Map<string, { content: any; fields: any[]; design: any; template: any }>>(
    new Map()
  );

  const handleApplyChatAction = useCallback(
    (action: any, actionId?: string): ApplyResult => {
      if (!editor) return { ok: false, message: 'Editor not ready' };
      if (actionId) {
        chatSnapshotsRef.current.set(actionId, {
          content: editor.getJSON(),
          fields: JSON.parse(JSON.stringify(fields)),
          design: { ...designSettings },
          template: template ? { ...template } : null,
        });
      }
      const result = applyChatAction({
        action,
        editor,
        fields,
        setTemplate,
        setFields,
        setDesignSettings,
        markUnsaved,
      });
      if (!result.ok && actionId) chatSnapshotsRef.current.delete(actionId);
      return result;
    },
    [editor, markUnsaved, setTemplate, setFields, setDesignSettings, fields, designSettings, template]
  );

  const handleUndoChatAction = useCallback(
    (actionId: string): boolean => {
      const snap = chatSnapshotsRef.current.get(actionId);
      if (!snap || !editor) return false;
      loadEditorContent(editor, snap.content);
      setFields(snap.fields);
      setDesignSettings(snap.design);
      if (snap.template) setTemplate(snap.template);
      chatSnapshotsRef.current.delete(actionId);
      markUnsaved();
      return true;
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
        sample_values: Object.fromEntries(Object.entries(sampleValues).filter(([, v]) => v && v.trim())),
      });
      setPreviewPages(res.pages || []);
    } catch (err: any) {
      showToast(err.message || 'Preview generation failed', 'error');
      setShowPreviewModal(false);
    } finally {
      setPreviewLoading(false);
    }
  };

  previewRef.current = handlePreview;

  // Keep the "Review & Publish (N)" badge in sync with AI-suggested blocks and fields.
  useEffect(() => {
    if (!editor) return;
    const count = () => {
      let n = 0;
      editor.state.doc.descendants((node: any) => {
        if (node.attrs?.ai_suggested) n += 1;
      });
      n += fields.filter((f) => f.ai_suggested).length;
      setUnreviewedAiCount(n);
    };
    count();
    editor.on('update', count);
    return () => {
      editor.off('update', count);
    };
  }, [editor, fields]);

  const handlePublish = async () => {
    if (!editor || !template) return;
    await saveNow();
    try {
      const res = await api.documents.publishTemplate(clubId, templateId);
      setTemplate((prev: any) => ({ ...prev, status: 'published' }));
      setUnreviewedAiCount(0);
      showToast(`"${res.name}" is published. Click "Use template" to fill it in.`, 'success');
    } catch (err: any) {
      if (err.status === 409 && err.detail?.unreviewed_items) {
        setUnreviewedModal(err.detail.unreviewed_items);
      } else {
        showToast(err.message || 'Publishing failed', 'error');
      }
    }
  };

  const handleApproveAllAi = async () => {
    setReviewingAi(true);
    try {
      await api.documents.reviewAiTemplate(clubId, templateId, { all: true });
      if (editor) {
        editor.commands.command(({ tr }: any) => {
          tr.doc.descendants((node: any, pos: number) => {
            if (node.attrs?.ai_suggested) tr.setNodeMarkup(pos, undefined, { ...node.attrs, ai_suggested: false });
          });
          return true;
        });
      }
      setFields((prev) => prev.map((f) => ({ ...f, ai_suggested: false })));
      setUnreviewedModal(null);
      await new Promise((resolve) => setTimeout(resolve, 0));
      await handlePublish();
    } catch (err: any) {
      showToast(err.message || 'Failed to approve AI content', 'error');
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
        showToast(`Template translated to ${targetLang === 'hi' ? 'Hindi' : 'Gujarati'}.`, 'success');
      }
    } catch (err: any) {
      showToast(err.message || 'Translation failed', 'error');
    } finally {
      setTranslating(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="text-center">
          <div className="w-8 h-8 border-3 border-brand-600 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
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
        onBack={handleBackSafe}
        editor={editor}
        zoom={zoom}
        onZoomChange={handleZoomChange}
        onOpenFindReplace={() => setShowFindReplace(true)}
        onOpenShortcuts={() => setShowShortcuts(true)}
        onPreview={handlePreview}
        onPublish={handlePublish}
        onOpenAddField={() => openLeft('fields')}
        previewLoading={previewLoading}
        unreviewedAiCount={unreviewedAiCount}
        isPublished={template?.status === 'published'}
        onCreateDocument={onCreateDocument}
        onTranslate={handleTranslate}
        translating={translating}
      />

      {/* In-app Toast / Notice Notification */}
      {notice && (
        <div
          role="status"
          className={`fixed top-14 left-1/2 -translate-x-1/2 z-50 px-4 py-2 rounded-xl shadow-xl text-xs font-semibold border flex items-center gap-2 animate-in fade-in slide-in-from-top-2 ${
            notice.tone === 'success'
              ? 'bg-emerald-50 text-emerald-800 border-emerald-300'
              : 'bg-rose-50 text-rose-800 border-rose-300'
          }`}
        >
          <span>{notice.text}</span>
          <button
            onClick={() => setNotice(null)}
            className="p-0.5 rounded hover:bg-black/5 text-slate-400 hover:text-slate-600"
            aria-label="Dismiss notice"
          >
            ✕
          </button>
        </div>
      )}

      <div className="flex flex-1 overflow-hidden relative">
        <EditorErrorBoundary title="Palette Error">
          <PalettePanel
            editor={editor}
            isOpen={leftOpen}
            onToggle={() => setLeftOpen(!leftOpen)}
            activeTab={leftTab}
            onTabChange={setLeftTab}
            onBlockInserted={() => isCompact() && setLeftOpen(false)}
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
                showToast('Applied official SVNIT style standards.', 'success');
              }
            }}
            sampleValues={sampleValues}
            onSampleChange={(key, value) => setSampleValues((prev) => ({ ...prev, [key]: value }))}
            onPreview={handlePreview}
          />
        </EditorErrorBoundary>

        <EditorErrorBoundary title="Canvas Editor Error">
          <Canvas
            editor={editor}
            zoom={zoom}
            designSettings={designSettings}
            watermarkText={designSettings.watermark}
            orientation={designSettings.orientation}
            margins={designSettings.margins}
            bubblePos={bubblePos}
            chipPopover={chipPopover}
            onCloseChipPopover={() => setChipPopover(null)}
            onUpdateChip={(updates: any) => {
              updateChip(updates);
              if (typeof updates?.label === 'string' && chipPopover?.fieldName) {
                setFields((prev) => prev.map((f) => (f.key === chipPopover.fieldName ? { ...f, label: updates.label } : f)));
              }
            }}
            onToggleChipRequired={toggleChipRequired}
            onToggleChipSensitive={toggleChipSensitive}
            onDeleteChip={deleteChip}
            selectedImageBlock={selectedImageBlock}
            onUpdateImageBlock={updateImageBlock}
            clubLogoOptions={clubLogoOptions}
            showSlashMenu={showSlashMenu}
            onCloseSlashMenu={() => setShowSlashMenu(false)}
            onOpenAddField={() => openLeft('fields')}
            fields={fields}
            inlinePicker={inlinePicker}
            onCloseInlinePicker={() => setInlinePicker(null)}
            onAddNewField={(newField) => {
              setFields((prev) => [...prev, newField]);
              markUnsaved();
            }}
            letterhead={letterhead}
          />
        </EditorErrorBoundary>

        <RightTabsPanel
          clubId={clubId}
          templateId={templateId}
          editor={editor}
          fields={fields}
          designSettings={designSettings}
          onApplyChatAction={handleApplyChatAction}
          onUndoChatAction={handleUndoChatAction}
          isOpen={rightOpen}
          onToggle={() => setRightOpen(!rightOpen)}
          activeTab={rightTab}
          onTabChange={setRightTab}
          isMobile={isMobile}
        />
      </div>


      {/* Phone / tablet action bar: the side panels have no room on small screens */}
      <nav className="lg:hidden shrink-0 grid grid-cols-4 border-t border-slate-200 bg-white" aria-label="Editor tools">
        {[
          { label: 'Add', icon: Plus, onClick: () => openLeft('blocks'), active: leftOpen && leftTab === 'blocks' },
          { label: 'Fields', icon: Tag, onClick: () => openLeft('fields'), active: leftOpen && leftTab === 'fields' },
          { label: 'Design', icon: Palette, onClick: () => openLeft('design'), active: leftOpen && leftTab === 'design' },
          { label: 'AI help', icon: Sparkles, onClick: () => openRight('chat'), active: rightOpen },
        ].map(({ label, icon: Icon, onClick, active }) => (
          <button
            key={label}
            type="button"
            onClick={onClick}
            aria-pressed={active}
            className={`flex flex-col items-center justify-center gap-0.5 min-h-[56px] text-[11px] font-semibold transition ${
              active ? 'text-brand-700 bg-brand-50' : 'text-slate-600 hover:bg-slate-50'
            }`}
          >
            <Icon className="w-5 h-5" />
            {label}
          </button>
        ))}
      </nav>

      <ShortcutsModal isOpen={showShortcuts} onClose={() => setShowShortcuts(false)} />
      <FindReplaceModal isOpen={showFindReplace} onClose={() => setShowFindReplace(false)} editor={editor} />
      <EditorTips />
      <PreviewModal isOpen={showPreviewModal} onClose={() => setShowPreviewModal(false)} loading={previewLoading} pages={previewPages} />
      <ValidationModal isOpen={showValidationModal} onClose={() => setShowValidationModal(false)} report={validationReport} />
      <UnreviewedAiModal items={unreviewedModal} onClose={() => setUnreviewedModal(null)} onApproveAll={handleApproveAllAi} reviewing={reviewingAi} />
    </div>
  );
};
