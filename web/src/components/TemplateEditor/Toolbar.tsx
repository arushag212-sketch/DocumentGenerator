import React from 'react';
import {
  ArrowLeft,
  Undo2,
  Redo2,
  Search,
  Command,
  Eye,
  CheckCircle2,
  AlertCircle,
  Save,
  ZoomIn,
  ZoomOut,
  Sparkles,
} from 'lucide-react';
import { SaveStatus } from './useEditorAutosave';

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
  onOpenFindReplace: () => void;
  onOpenShortcuts: () => void;
  onPreview: () => void;
  onPublish: () => void;
  previewLoading?: boolean;
  unreviewedAiCount?: number;
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
  previewLoading = false,
  unreviewedAiCount = 0,
}) => {
  const canUndo = editor?.can?.().undo?.() ?? false;
  const canRedo = editor?.can?.().redo?.() ?? false;

  const handleZoomIn = () => {
    if (zoom < 1.5) onZoomChange(Math.min(1.5, Math.round((zoom + 0.1) * 10) / 10));
  };

  const handleZoomOut = () => {
    if (zoom > 0.6) onZoomChange(Math.max(0.6, Math.round((zoom - 0.1) * 10) / 10));
  };

  return (
    <header className="sticky top-0 z-30 bg-white/95 backdrop-blur border-b border-slate-200 px-4 py-2 flex items-center justify-between shadow-sm">
      {/* Left: Navigation and Template Identity */}
      <div className="flex items-center gap-3">
        <button
          onClick={onBack}
          className="p-1.5 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition"
          title="Back to templates"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>

        <div className="flex flex-col">
          <div className="flex items-center gap-2">
            <h1 className="font-bold text-slate-900 text-sm md:text-base leading-tight truncate max-w-[220px] md:max-w-md">
              {templateName || 'Untitled Template'}
            </h1>
            <span className="text-[10px] uppercase font-semibold px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 border border-slate-200">
              {category}
            </span>
            {version !== undefined && (
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-700 border border-indigo-200">
                v{version}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Center: Undo/Redo, Zoom, Search, Shortcuts */}
      <div className="hidden sm:flex items-center gap-1 bg-slate-50 border border-slate-200 rounded-lg p-0.5 shadow-inner">
        <button
          onClick={() => editor?.chain().focus().undo().run()}
          disabled={!canUndo}
          className="p-1.5 rounded text-slate-600 hover:text-slate-900 hover:bg-white disabled:opacity-30 disabled:hover:bg-transparent transition"
          title="Undo (Ctrl+Z)"
        >
          <Undo2 className="w-4 h-4" />
        </button>
        <button
          onClick={() => editor?.chain().focus().redo().run()}
          disabled={!canRedo}
          className="p-1.5 rounded text-slate-600 hover:text-slate-900 hover:bg-white disabled:opacity-30 disabled:hover:bg-transparent transition"
          title="Redo (Ctrl+Y)"
        >
          <Redo2 className="w-4 h-4" />
        </button>

        <div className="w-px h-4 bg-slate-200 mx-1" />

        <button
          onClick={handleZoomOut}
          disabled={zoom <= 0.6}
          className="p-1.5 rounded text-slate-600 hover:text-slate-900 hover:bg-white disabled:opacity-30 transition"
          title="Zoom out"
        >
          <ZoomOut className="w-3.5 h-3.5" />
        </button>
        <span className="text-[11px] font-mono font-medium text-slate-600 px-1 w-10 text-center select-none">
          {Math.round(zoom * 100)}%
        </span>
        <button
          onClick={handleZoomIn}
          disabled={zoom >= 1.5}
          className="p-1.5 rounded text-slate-600 hover:text-slate-900 hover:bg-white disabled:opacity-30 transition"
          title="Zoom in"
        >
          <ZoomIn className="w-3.5 h-3.5" />
        </button>

        <div className="w-px h-4 bg-slate-200 mx-1" />

        <button
          onClick={onOpenFindReplace}
          className="p-1.5 rounded text-slate-600 hover:text-slate-900 hover:bg-white transition"
          title="Find and Replace (Ctrl+F)"
        >
          <Search className="w-4 h-4" />
        </button>
        <button
          onClick={onOpenShortcuts}
          className="p-1.5 rounded text-slate-600 hover:text-slate-900 hover:bg-white transition"
          title="Keyboard Shortcuts Cheat Sheet"
        >
          <Command className="w-4 h-4" />
        </button>
      </div>

      {/* Right: Autosave Status, Preview & Publish */}
      <div className="flex items-center gap-2.5">
        {/* Autosave Status Pill */}
        <div
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium transition ${
            saveStatus === 'saved'
              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
              : saveStatus === 'saving'
              ? 'bg-amber-50 text-amber-700 border border-amber-200'
              : saveStatus === 'conflict'
              ? 'bg-rose-50 text-rose-700 border border-rose-300'
              : 'bg-slate-100 text-slate-600 border border-slate-200'
          }`}
          title={conflictMessage || undefined}
        >
          {saveStatus === 'saved' && (
            <>
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
              <span>Saved</span>
            </>
          )}
          {saveStatus === 'saving' && (
            <>
              <Save className="w-3.5 h-3.5 animate-pulse text-amber-600" />
              <span>Saving…</span>
            </>
          )}
          {saveStatus === 'unsaved' && (
            <>
              <div className="w-2 h-2 rounded-full bg-amber-400" />
              <span>Unsaved</span>
            </>
          )}
          {saveStatus === 'conflict' && (
            <>
              <AlertCircle className="w-3.5 h-3.5 text-rose-600" />
              <span>Version Conflict</span>
            </>
          )}
        </div>

        {/* Live Preview Button */}
        <button
          onClick={onPreview}
          disabled={previewLoading}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-white border border-slate-300 text-slate-700 hover:bg-slate-50 shadow-sm transition"
        >
          <Eye className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">Preview</span>
        </button>

        {/* Publish Button */}
        <button
          onClick={onPublish}
          className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm transition"
        >
          {unreviewedAiCount > 0 ? (
            <>
              <Sparkles className="w-3.5 h-3.5 text-amber-300" />
              <span>Review & Publish ({unreviewedAiCount})</span>
            </>
          ) : (
            <span>Publish</span>
          )}
        </button>
      </div>
    </header>
  );
};
