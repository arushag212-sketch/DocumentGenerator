import React, { useState } from 'react';
import {
  ArrowLeft,
  Undo2,
  Redo2,
  ZoomIn,
  ZoomOut,
  Bold,
  Italic,
  Underline as UnderlineIcon,
  AlignLeft,
  AlignCenter,
  AlignRight,
  AlignJustify,
  Heading1,
  Heading2,
  Pilcrow,
  Table as TableIcon,
  Image as ImageIcon,
  CheckSquare,
  Minus,
  Eye,
  CheckCircle2,
  Save,
  AlertCircle,
  FilePlus2,
  Wand2,
  Search,
  HelpCircle,
  Languages,
} from 'lucide-react';
import { SaveStatus } from './useEditorAutosave';
import { FontControls } from './FontControls';
import { insertInfoTable, insertSignatureGrid, insertImageBlock, safeInsertBlock } from './extensions';

interface ToolbarProps {
  templateName: string;
  category?: string;
  version?: number;
  saveStatus: SaveStatus;
  conflictMessage?: string | null;
  onBack: () => void;
  editor: any;
  zoom: number;
  onZoomChange: (newZoom: number) => void;
  onOpenFindReplace?: () => void;
  onOpenShortcuts?: () => void;
  onPreview: () => void;
  onPublish: () => void;
  onOpenAddField?: () => void;
  previewLoading?: boolean;
  unreviewedAiCount?: number;
  onTranslate?: (lang: 'hi' | 'gu') => void;
  translating?: boolean;
  isPublished?: boolean;
  onCreateDocument?: () => void;
}

export const Toolbar: React.FC<ToolbarProps> = ({
  templateName,
  category = 'General',
  version,
  saveStatus,
  conflictMessage,
  onBack,
  editor,
  zoom,
  onZoomChange,
  onOpenFindReplace,
  onOpenShortcuts,
  onPreview,
  onPublish,
  onOpenAddField,
  previewLoading = false,
  unreviewedAiCount = 0,
  isPublished = false,
  onCreateDocument,
  onTranslate,
  translating = false,
}) => {
  const [showTranslateMenu, setShowTranslateMenu] = useState(false);

  const canUndo = editor?.can?.().undo?.() ?? false;
  const canRedo = editor?.can?.().redo?.() ?? false;

  const handleZoomIn = () => {
    if (zoom < 1.5) onZoomChange(Math.min(1.5, Math.round((zoom + 0.1) * 10) / 10));
  };

  const handleZoomOut = () => {
    if (zoom > 0.6) onZoomChange(Math.max(0.6, Math.round((zoom - 0.1) * 10) / 10));
  };

  return (
    <header className="sticky top-0 z-30 bg-white/95 backdrop-blur border-b border-slate-200 px-3 py-1.5 flex items-center justify-between shadow-xs select-none">
      {/* Left: Navigation and Template Identity */}
      <div className="flex items-center gap-2.5 shrink-0">
        <button
          onClick={onBack}
          className="p-1.5 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition focus:outline-none focus:ring-2 focus:ring-brand-500/20"
          title="Back to templates (Esc)"
          aria-label="Back to templates"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>

        <div className="flex flex-col">
          <div className="flex items-center gap-1.5">
            <h1 className="font-bold text-slate-900 text-xs sm:text-sm leading-tight truncate max-w-[140px] sm:max-w-[200px] lg:max-w-xs">
              {templateName || 'Untitled Template'}
            </h1>
            <span className="hidden sm:inline-block text-[10px] uppercase font-semibold px-1.5 py-0.2 rounded-full bg-slate-100 text-slate-600 border border-slate-200">
              {category}
            </span>
            {version !== undefined && (
              <span className="text-[10px] font-mono px-1 py-0.2 rounded bg-brand-50 text-brand-700 border border-brand-200">
                v{version}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Center: Comprehensive Editor Toolbar */}
      <div className="flex items-center gap-0.5 overflow-x-auto py-0.5 px-1 max-w-full">
        {/* Group 1: Undo / Redo */}
        <div className="flex items-center bg-slate-50 border border-slate-200 rounded-lg p-0.5">
          <button
            onClick={() => editor?.chain().focus().undo().run()}
            disabled={!canUndo}
            className="p-1.5 rounded text-slate-600 hover:text-slate-900 hover:bg-white disabled:opacity-30 disabled:hover:bg-transparent transition focus:outline-none focus:ring-1 focus:ring-brand-500"
            title="Undo (Ctrl+Z)"
            aria-label="Undo"
          >
            <Undo2 className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => editor?.chain().focus().redo().run()}
            disabled={!canRedo}
            className="p-1.5 rounded text-slate-600 hover:text-slate-900 hover:bg-white disabled:opacity-30 disabled:hover:bg-transparent transition focus:outline-none focus:ring-1 focus:ring-brand-500"
            title="Redo (Ctrl+Y)"
            aria-label="Redo"
          >
            <Redo2 className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="w-px h-4 bg-slate-200 mx-0.5 shrink-0" />

        {/* Group 2: Text Style (Heading 1/2, Normal) */}
        <div className="flex items-center bg-slate-50 border border-slate-200 rounded-lg p-0.5">
          <button
            onClick={() => editor?.chain().focus().setParagraph().run()}
            className={`p-1.5 rounded transition focus:outline-none focus:ring-1 focus:ring-brand-500 ${
              editor?.isActive('paragraph') && !editor?.isActive('heading')
                ? 'bg-white text-brand-700 shadow-xs font-bold'
                : 'text-slate-600 hover:text-slate-900 hover:bg-white'
            }`}
            title="Normal Paragraph (Ctrl+Alt+0)"
            aria-label="Normal text"
          >
            <Pilcrow className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => editor?.chain().focus().toggleHeading({ level: 1 }).run()}
            className={`p-1.5 rounded transition focus:outline-none focus:ring-1 focus:ring-brand-500 ${
              editor?.isActive('heading', { level: 1 })
                ? 'bg-white text-brand-700 shadow-xs font-bold'
                : 'text-slate-600 hover:text-slate-900 hover:bg-white'
            }`}
            title="Heading 1 (Ctrl+Alt+1)"
            aria-label="Heading 1"
          >
            <Heading1 className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => editor?.chain().focus().toggleHeading({ level: 2 }).run()}
            className={`p-1.5 rounded transition focus:outline-none focus:ring-1 focus:ring-brand-500 ${
              editor?.isActive('heading', { level: 2 })
                ? 'bg-white text-brand-700 shadow-xs font-bold'
                : 'text-slate-600 hover:text-slate-900 hover:bg-white'
            }`}
            title="Heading 2 (Ctrl+Alt+2)"
            aria-label="Heading 2"
          >
            <Heading2 className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="w-px h-4 bg-slate-200 mx-0.5 shrink-0" />

        {/* Group 3: Font Family + Size */}
        <div className="hidden md:flex items-center">
          <FontControls variant="toolbar" editor={editor} />
        </div>

        <div className="w-px h-4 bg-slate-200 mx-0.5 shrink-0" />

        {/* Group 4: B / I / U */}
        <div className="flex items-center bg-slate-50 border border-slate-200 rounded-lg p-0.5">
          <button
            onClick={() => editor?.chain().focus().toggleBold().run()}
            className={`p-1.5 rounded transition focus:outline-none focus:ring-1 focus:ring-brand-500 ${
              editor?.isActive('bold') ? 'bg-white text-brand-700 shadow-xs font-bold' : 'text-slate-600 hover:text-slate-900 hover:bg-white'
            }`}
            title="Bold (Ctrl+B)"
            aria-label="Bold"
          >
            <Bold className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => editor?.chain().focus().toggleItalic().run()}
            className={`p-1.5 rounded transition focus:outline-none focus:ring-1 focus:ring-brand-500 ${
              editor?.isActive('italic') ? 'bg-white text-brand-700 shadow-xs font-bold' : 'text-slate-600 hover:text-slate-900 hover:bg-white'
            }`}
            title="Italic (Ctrl+I)"
            aria-label="Italic"
          >
            <Italic className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => editor?.chain().focus().toggleUnderline().run()}
            className={`p-1.5 rounded transition focus:outline-none focus:ring-1 focus:ring-brand-500 ${
              editor?.isActive('underline') ? 'bg-white text-brand-700 shadow-xs font-bold' : 'text-slate-600 hover:text-slate-900 hover:bg-white'
            }`}
            title="Underline (Ctrl+U)"
            aria-label="Underline"
          >
            <UnderlineIcon className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="w-px h-4 bg-slate-200 mx-0.5 shrink-0" />

        {/* Group 5: Align */}
        <div className="hidden sm:flex items-center bg-slate-50 border border-slate-200 rounded-lg p-0.5">
          <button
            onClick={() => editor?.chain().focus().setTextAlign('left').run()}
            className={`p-1.5 rounded transition focus:outline-none focus:ring-1 focus:ring-brand-500 ${
              editor?.isActive({ textAlign: 'left' }) ? 'bg-white text-brand-700 shadow-xs' : 'text-slate-600 hover:text-slate-900 hover:bg-white'
            }`}
            title="Align Left (Ctrl+Shift+L)"
            aria-label="Align left"
          >
            <AlignLeft className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => editor?.chain().focus().setTextAlign('center').run()}
            className={`p-1.5 rounded transition focus:outline-none focus:ring-1 focus:ring-brand-500 ${
              editor?.isActive({ textAlign: 'center' }) ? 'bg-white text-brand-700 shadow-xs' : 'text-slate-600 hover:text-slate-900 hover:bg-white'
            }`}
            title="Align Center (Ctrl+Shift+E)"
            aria-label="Align center"
          >
            <AlignCenter className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => editor?.chain().focus().setTextAlign('right').run()}
            className={`p-1.5 rounded transition focus:outline-none focus:ring-1 focus:ring-brand-500 ${
              editor?.isActive({ textAlign: 'right' }) ? 'bg-white text-brand-700 shadow-xs' : 'text-slate-600 hover:text-slate-900 hover:bg-white'
            }`}
            title="Align Right (Ctrl+Shift+R)"
            aria-label="Align right"
          >
            <AlignRight className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => editor?.chain().focus().setTextAlign('justify').run()}
            className={`p-1.5 rounded transition focus:outline-none focus:ring-1 focus:ring-brand-500 ${
              editor?.isActive({ textAlign: 'justify' }) ? 'bg-white text-brand-700 shadow-xs' : 'text-slate-600 hover:text-slate-900 hover:bg-white'
            }`}
            title="Justify (Ctrl+Shift+J)"
            aria-label="Justify text"
          >
            <AlignJustify className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="w-px h-4 bg-slate-200 mx-0.5 shrink-0" />

        {/* Group 6: Insert (Field, Table, Image, Signature, Divider) */}
        <div className="flex items-center bg-slate-50 border border-slate-200 rounded-lg p-0.5">
          <button
            onClick={onOpenAddField}
            className="flex items-center gap-1 px-2 py-1 rounded text-xs font-semibold text-brand-700 hover:bg-white hover:shadow-xs transition focus:outline-none focus:ring-1 focus:ring-brand-500"
            title="Insert Dynamic Field (type '{{' or click)"
            aria-label="Insert field"
          >
            <Wand2 className="w-3.5 h-3.5 text-brand-600" />
            <span className="hidden xl:inline">Field</span>
          </button>
          <button
            onClick={() => editor && insertInfoTable(editor)}
            className="p-1.5 rounded text-slate-600 hover:text-slate-900 hover:bg-white transition focus:outline-none focus:ring-1 focus:ring-brand-500"
            title="Insert Table"
            aria-label="Insert table"
          >
            <TableIcon className="w-3.5 h-3.5 text-emerald-600" />
          </button>
          <button
            onClick={() => editor && insertImageBlock(editor, { imageType: 'custom', alt: 'Image' })}
            className="p-1.5 rounded text-slate-600 hover:text-slate-900 hover:bg-white transition focus:outline-none focus:ring-1 focus:ring-brand-500"
            title="Insert Image"
            aria-label="Insert image"
          >
            <ImageIcon className="w-3.5 h-3.5 text-brand-600" />
          </button>
          <button
            onClick={() => editor && insertSignatureGrid(editor, 2)}
            className="p-1.5 rounded text-slate-600 hover:text-slate-900 hover:bg-white transition focus:outline-none focus:ring-1 focus:ring-brand-500"
            title="Insert Signature Box"
            aria-label="Insert signature box"
          >
            <CheckSquare className="w-3.5 h-3.5 text-amber-600" />
          </button>
          <button
            onClick={() => editor && safeInsertBlock(editor, { type: 'pageBreak' })}
            className="p-1.5 rounded text-slate-600 hover:text-slate-900 hover:bg-white transition focus:outline-none focus:ring-1 focus:ring-brand-500"
            title="Insert Divider / Page Break"
            aria-label="Insert divider"
          >
            <Minus className="w-3.5 h-3.5 text-slate-500" />
          </button>
        </div>

        <div className="w-px h-4 bg-slate-200 mx-0.5 shrink-0" />

        {/* Group 7: Zoom */}
        <div className="hidden lg:flex items-center bg-slate-50 border border-slate-200 rounded-lg p-0.5">
          <button
            onClick={handleZoomOut}
            disabled={zoom <= 0.6}
            className="p-1.5 rounded text-slate-600 hover:text-slate-900 hover:bg-white disabled:opacity-30 transition focus:outline-none focus:ring-1 focus:ring-brand-500"
            title="Zoom out"
            aria-label="Zoom out"
          >
            <ZoomOut className="w-3 h-3" />
          </button>
          <span className="text-[11px] font-mono font-medium text-slate-600 px-1 w-9 text-center select-none">
            {Math.round(zoom * 100)}%
          </span>
          <button
            onClick={handleZoomIn}
            disabled={zoom >= 1.5}
            className="p-1.5 rounded text-slate-600 hover:text-slate-900 hover:bg-white disabled:opacity-30 transition focus:outline-none focus:ring-1 focus:ring-brand-500"
            title="Zoom in"
            aria-label="Zoom in"
          >
            <ZoomIn className="w-3 h-3" />
          </button>
        </div>

        {/* Utilities: Find & Replace, Shortcuts, Language */}
        <div className="hidden xl:flex items-center gap-0.5 ml-1">
          {onOpenFindReplace && (
            <button
              onClick={onOpenFindReplace}
              className="p-1.5 rounded text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition"
              title="Find and replace (Ctrl+F)"
              aria-label="Find and replace"
            >
              <Search className="w-3.5 h-3.5" />
            </button>
          )}

          {onOpenShortcuts && (
            <button
              onClick={onOpenShortcuts}
              className="p-1.5 rounded text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition"
              title="Keyboard shortcuts (?)"
              aria-label="Keyboard shortcuts"
            >
              <HelpCircle className="w-3.5 h-3.5" />
            </button>
          )}

          {onTranslate && (
            <div className="relative">
              <button
                onClick={() => setShowTranslateMenu(!showTranslateMenu)}
                disabled={translating}
                className="p-1.5 rounded text-slate-500 hover:text-slate-800 hover:bg-slate-100 disabled:opacity-40 transition"
                title="Translate template"
                aria-label="Translate template"
              >
                <Languages className="w-3.5 h-3.5" />
              </button>
              {showTranslateMenu && (
                <div className="absolute right-0 top-full mt-1 w-32 bg-white rounded-lg shadow-lg border border-slate-200 py-1 z-50 text-xs">
                  <button
                    onClick={() => {
                      setShowTranslateMenu(false);
                      onTranslate('hi');
                    }}
                    className="w-full text-left px-3 py-1.5 hover:bg-slate-50 text-slate-700"
                  >
                    Hindi (हिन्दी)
                  </button>
                  <button
                    onClick={() => {
                      setShowTranslateMenu(false);
                      onTranslate('gu');
                    }}
                    className="w-full text-left px-3 py-1.5 hover:bg-slate-50 text-slate-700"
                  >
                    Gujarati (ગુજરાતી)
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Right: Autosave Status, Preview, & Done / Use Template */}
      <div className="flex items-center gap-2 shrink-0">
        {/* Autosave Status Pill */}
        <div
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium transition ${
            saveStatus === 'saved'
              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
              : saveStatus === 'saving'
              ? 'bg-amber-50 text-amber-700 border border-amber-200'
              : saveStatus === 'conflict'
              ? 'bg-rose-50 text-rose-700 border border-rose-300'
              : 'bg-amber-50 text-amber-800 border border-amber-300'
          }`}
          title={conflictMessage || (saveStatus === 'unsaved' ? 'Unsaved changes (Ctrl+S to save)' : 'Saved')}
        >
          {saveStatus === 'saved' && (
            <>
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
              <span className="hidden sm:inline">Saved</span>
            </>
          )}
          {saveStatus === 'saving' && (
            <>
              <Save className="w-3.5 h-3.5 animate-pulse text-amber-600" />
              <span className="hidden sm:inline">Saving…</span>
            </>
          )}
          {saveStatus === 'unsaved' && (
            <>
              <div className="w-2 h-2 rounded-full bg-amber-500" />
              <span className="hidden sm:inline">Unsaved changes</span>
            </>
          )}
          {saveStatus === 'conflict' && (
            <>
              <AlertCircle className="w-3.5 h-3.5 text-rose-600" />
              <span className="hidden sm:inline">Conflict</span>
            </>
          )}
        </div>

        {/* Live Preview Button */}
        <button
          onClick={onPreview}
          disabled={previewLoading}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-white border border-slate-300 text-slate-700 hover:bg-slate-50 shadow-xs transition focus:outline-none focus:ring-2 focus:ring-brand-500/20"
          title="Live Preview (Ctrl+P)"
          aria-label="Preview document"
        >
          <Eye className="w-3.5 h-3.5 text-brand-600" />
          <span>Preview</span>
        </button>

        {/* Primary Action Button: Done / Use template / Publish */}
        {isPublished && onCreateDocument ? (
          <button
            onClick={onCreateDocument}
            title="Fill this template and generate official DOCX/PDF"
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-emerald-600 hover:bg-emerald-700 text-white shadow-xs transition focus:outline-none focus:ring-2 focus:ring-emerald-500/20"
          >
            <FilePlus2 className="w-3.5 h-3.5" />
            <span>Use template</span>
          </button>
        ) : (
          <button
            onClick={onPublish}
            title={unreviewedAiCount > 0 ? 'Review unreviewed AI blocks' : 'Publish and finish template'}
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-brand-600 hover:bg-brand-700 text-white shadow-xs transition focus:outline-none focus:ring-2 focus:ring-brand-500/20"
          >
            {unreviewedAiCount > 0 ? (
              <>
                <Wand2 className="w-3.5 h-3.5 text-amber-300" />
                <span>Review ({unreviewedAiCount})</span>
              </>
            ) : (
              <span>Done</span>
            )}
          </button>
        )}
      </div>
    </header>
  );
};
