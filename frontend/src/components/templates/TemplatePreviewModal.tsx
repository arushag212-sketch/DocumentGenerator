import React, { useEffect, useRef, useState } from 'react';
import { X, PlusCircle, Copy, FileText, ZoomIn, ZoomOut, AlertCircle } from 'lucide-react';
import { api } from '../../api/client';
import { TemplateGalleryItem } from '../../types';

/**
 * Full-page look at a template before using or editing it: every page filled with sample
 * values, printed with the viewing club's own letterhead.
 */
export const TemplatePreviewModal: React.FC<{
  clubId: string | number;
  template: TemplateGalleryItem;
  canManage: boolean;
  onClose: () => void;
  onUse: () => void;
  onCustomize?: () => void;
  onEdit?: () => void;
}> = ({ clubId, template, canManage, onClose, onUse, onCustomize, onEdit }) => {
  const [pages, setPages] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    let alive = true;
    setPages(null);
    setError(null);
    api.documents
      .getTemplateSamplePages(clubId, template.id)
      .then((res) => alive && setPages(res.pages))
      .catch((e: any) => alive && setError(e?.detail || e?.message || 'The preview could not be prepared.'));
    return () => {
      alive = false;
    };
  }, [clubId, template.id]);

  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6" role="dialog" aria-modal="true" aria-labelledby="tpl-preview-title">
      <div className="absolute inset-0 bg-slate-900/50" onClick={onClose} />
      <div className="relative w-full max-w-4xl h-full max-h-[92vh] bg-white rounded-xl shadow-2xl flex flex-col overflow-hidden">
        <header className="flex items-start justify-between gap-3 px-5 py-3.5 border-b border-slate-200">
          <div className="min-w-0">
            <h2 id="tpl-preview-title" className="section-title truncate">{template.name}</h2>
            <p className="text-sm text-slate-500 truncate">
              {template.is_system ? 'Built-in template' : 'Club template'} · sample values, with your club's letterhead
              {pages ? ` · ${pages.length} page${pages.length === 1 ? '' : 's'}` : ''}
            </p>
          </div>
          <div className="flex items-center gap-1 flex-shrink-0">
            <button type="button" className="btn-ghost !p-1.5" onClick={() => setZoom((z) => Math.max(0.6, +(z - 0.2).toFixed(1)))} aria-label="Zoom out" title="Zoom out">
              <ZoomOut className="w-4 h-4" />
            </button>
            <span className="text-xs text-slate-500 w-10 text-center tabular-nums">{Math.round(zoom * 100)}%</span>
            <button type="button" className="btn-ghost !p-1.5" onClick={() => setZoom((z) => Math.min(2, +(z + 0.2).toFixed(1)))} aria-label="Zoom in" title="Zoom in">
              <ZoomIn className="w-4 h-4" />
            </button>
            <button ref={closeRef} type="button" className="btn-ghost !p-1.5 ml-1" onClick={onClose} aria-label="Close preview">
              <X className="w-4 h-4" />
            </button>
          </div>
        </header>

        <div className="flex-1 overflow-auto bg-slate-100 px-4 py-6">
          {error ? (
            <div className="max-w-md mx-auto mt-16 text-center">
              <AlertCircle className="w-8 h-8 text-slate-400 mx-auto mb-2" />
              <p className="text-sm text-slate-700">{error}</p>
            </div>
          ) : !pages ? (
            <div className="flex flex-col items-center justify-center gap-3 mt-24 text-sm text-slate-500" role="status">
              <span className="h-6 w-6 border-2 border-brand-700 border-t-transparent rounded-full animate-spin" />
              Preparing the preview… the first time takes a few seconds.
            </div>
          ) : (
            <div className="mx-auto space-y-5" style={{ width: `${Math.round(720 * zoom)}px`, maxWidth: zoom <= 1 ? '100%' : undefined }}>
              {pages.map((src, i) => (
                <img
                  key={src}
                  src={src}
                  alt={`Page ${i + 1} of ${pages.length}`}
                  className="w-full bg-white shadow-md border border-slate-200"
                  loading={i === 0 ? 'eager' : 'lazy'}
                />
              ))}
            </div>
          )}
        </div>

        <footer className="flex flex-wrap items-center justify-end gap-2 px-5 py-3 border-t border-slate-200 bg-white">
          {template.is_system && canManage && onCustomize && (
            <button type="button" className="btn-secondary" onClick={onCustomize}>
              <Copy className="w-4 h-4" /> Customize
            </button>
          )}
          {!template.is_system && canManage && onEdit && (
            <button type="button" className="btn-secondary" onClick={onEdit}>
              <FileText className="w-4 h-4" /> Edit
            </button>
          )}
          <button type="button" className="btn-primary" onClick={onUse}>
            <PlusCircle className="w-4 h-4" /> Use template
          </button>
        </footer>
      </div>
    </div>
  );
};
