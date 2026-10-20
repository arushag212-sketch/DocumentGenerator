import React, { useState } from 'react';
import { Eye, RefreshCw, X, CheckCircle2, AlertCircle, ZoomIn, Maximize2, Minimize2 } from 'lucide-react';

interface PreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  loading: boolean;
  pages: string[];
  orientation?: 'portrait' | 'landscape';
}

export const PreviewModal: React.FC<PreviewModalProps> = ({
  isOpen,
  onClose,
  loading,
  pages,
  orientation = 'portrait',
}) => {
  const [zoomMode, setZoomMode] = useState<'fit-page' | 'fit-width' | '100%'>('fit-page');

  if (!isOpen) return null;

  const isLandscape = orientation === 'landscape';

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="preview-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 sm:p-6 animate-in fade-in"
    >
      <div className="bg-white rounded-2xl shadow-2xl max-w-5xl w-full max-h-[92vh] flex flex-col overflow-hidden border border-slate-200">
        {/* Header */}
        <div className="px-6 py-3.5 border-b border-slate-200 flex items-center justify-between bg-white shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 rounded-lg bg-brand-50 text-brand-700">
              <Eye className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 id="preview-modal-title" className="font-bold text-slate-900 text-sm sm:text-base leading-tight">
                  Template Live Preview
                </h3>
                <span className="text-[11px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full font-medium border border-slate-200">
                  Dummy Data Render
                </span>
                <span className="text-[11px] uppercase tracking-wider font-mono font-semibold px-2 py-0.5 rounded-full bg-brand-50 text-brand-700 border border-brand-200">
                  {isLandscape ? 'Landscape (A4)' : 'Portrait (A4)'}
                </span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Zoom Controls */}
            {!loading && pages.length > 0 && (
              <div className="hidden sm:flex items-center gap-1 bg-slate-100 p-0.5 rounded-lg border border-slate-200 text-xs font-medium mr-2">
                <button
                  type="button"
                  onClick={() => setZoomMode('fit-page')}
                  className={`px-2 py-1 rounded-md transition ${
                    zoomMode === 'fit-page'
                      ? 'bg-white text-slate-800 shadow-xs font-semibold'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                  title="Fit entire page to view"
                >
                  <Minimize2 className="w-3.5 h-3.5 inline mr-1" />
                  Fit Page
                </button>
                <button
                  type="button"
                  onClick={() => setZoomMode('fit-width')}
                  className={`px-2 py-1 rounded-md transition ${
                    zoomMode === 'fit-width'
                      ? 'bg-white text-slate-800 shadow-xs font-semibold'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                  title="Fit page width to container"
                >
                  <Maximize2 className="w-3.5 h-3.5 inline mr-1" />
                  Fit Width
                </button>
                <button
                  type="button"
                  onClick={() => setZoomMode('100%')}
                  className={`px-2 py-1 rounded-md transition ${
                    zoomMode === '100%'
                      ? 'bg-white text-slate-800 shadow-xs font-semibold'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                  title="Natural 100% zoom"
                >
                  <ZoomIn className="w-3.5 h-3.5 inline mr-1" />
                  100%
                </button>
              </div>
            )}

            <button
              onClick={onClose}
              aria-label="Close preview"
              className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-6 bg-slate-100/80 flex flex-col items-center gap-8">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-28 text-slate-500 animate-in fade-in duration-200">
              <div className="p-4 rounded-2xl bg-white shadow-md border border-slate-200 mb-4 flex items-center justify-center">
                <RefreshCw className="w-8 h-8 animate-spin text-brand-600" />
              </div>
              <p className="text-base font-bold text-slate-800">Preparing preview…</p>
              <p className="text-xs text-slate-500 mt-1">Compiling DOCX & rendering sample PDF pages</p>
            </div>
          ) : pages.length === 0 ? (
            <div className="p-16 text-center text-slate-500 bg-white rounded-xl border border-slate-200 max-w-md my-auto">
              <AlertCircle className="w-8 h-8 text-slate-400 mx-auto mb-2" />
              <p className="text-sm font-semibold text-slate-700">No preview generated</p>
              <p className="text-xs text-slate-500 mt-1">Please ensure the template has content and try again.</p>
            </div>
          ) : (
            pages.map((pageSrc, idx) => {
              // Sizing logic based on orientation & zoomMode
              let containerClasses = 'bg-white shadow-xl border border-slate-300 rounded-lg overflow-hidden transition-all duration-150 flex flex-col items-center';
              let imgClasses = 'block h-auto shadow-xs';

              if (isLandscape) {
                // Landscape page
                if (zoomMode === 'fit-page') {
                  containerClasses += ' max-w-[850px] w-full';
                  imgClasses += ' w-full max-h-[72vh] object-contain';
                } else if (zoomMode === 'fit-width') {
                  containerClasses += ' w-full max-w-full';
                  imgClasses += ' w-full';
                } else {
                  containerClasses += ' w-[1050px] max-w-none';
                  imgClasses += ' w-full';
                }
              } else {
                // Portrait page: tall and narrow
                if (zoomMode === 'fit-page') {
                  containerClasses += ' max-w-[550px] w-full';
                  imgClasses += ' max-h-[74vh] w-auto max-w-full object-contain';
                } else if (zoomMode === 'fit-width') {
                  containerClasses += ' w-full max-w-[760px]';
                  imgClasses += ' w-full';
                } else {
                  containerClasses += ' w-[840px] max-w-none';
                  imgClasses += ' w-full';
                }
              }

              return (
                <div key={idx} className="flex flex-col items-center gap-2">
                  <div className="flex items-center justify-between w-full px-1 text-xs font-medium text-slate-500">
                    <span>Page {idx + 1} of {pages.length}</span>
                    <span className="uppercase text-[10px] tracking-wider text-slate-400 font-mono">
                      {isLandscape ? 'Landscape' : 'Portrait'} A4
                    </span>
                  </div>
                  <div className={containerClasses}>
                    <img
                      src={pageSrc}
                      alt={`Page ${idx + 1}`}
                      className={imgClasses}
                      loading="lazy"
                    />
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-200 flex items-center justify-between bg-white shrink-0">
          <div className="text-xs text-slate-500">
            {pages.length > 0 && <span>Showing {pages.length} {pages.length === 1 ? 'page' : 'pages'} with sample values</span>}
          </div>
          <button
            onClick={onClose}
            className="px-4 py-2 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

interface ValidationModalProps {
  isOpen: boolean;
  onClose: () => void;
  report: any;
}

export const ValidationModal: React.FC<ValidationModalProps> = ({
  isOpen,
  onClose,
  report,
}) => {
  if (!isOpen || !report) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="validation-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-xs p-6 animate-in fade-in"
    >
      <div className="bg-white rounded-2xl shadow-xl max-w-xl w-full p-6 border border-slate-200">
        <div className="flex items-center justify-between pb-3 border-b border-slate-200 mb-4">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-5 h-5 text-emerald-600" />
            <h3 id="validation-modal-title" className="font-bold text-slate-800 text-base">
              Compiler Validation Report
            </h3>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="text-xs text-slate-600 flex flex-col gap-3 max-h-96 overflow-y-auto">
          <div className="p-3 bg-emerald-50 text-emerald-800 rounded-xl border border-emerald-200 font-medium">
            Document successfully compiled to python-docx and verified via SandboxedEnvironment.
          </div>
          <div>
            <span className="font-semibold text-slate-700">Tags Extracted: </span>
            <span className="font-mono">{report.extracted_tags?.join(', ') || 'None'}</span>
          </div>
        </div>

        <div className="mt-6 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 text-xs font-semibold text-white bg-brand-600 hover:bg-brand-700 rounded-lg shadow-xs"
          >
            OK
          </button>
        </div>
      </div>
    </div>
  );
};

interface UnreviewedAiModalProps {
  items: any[] | null;
  onClose: () => void;
  onApproveAll: () => void;
  reviewing: boolean;
}

export const UnreviewedAiModal: React.FC<UnreviewedAiModalProps> = ({
  items,
  onClose,
  onApproveAll,
  reviewing,
}) => {
  if (!items) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="unreviewed-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-6 animate-in fade-in"
    >
      <div className="bg-white rounded-2xl shadow-xl max-w-lg w-full p-6 border border-amber-200">
        <div className="flex items-center gap-3 mb-4 text-amber-700">
          <AlertCircle className="w-6 h-6 text-amber-600 shrink-0" />
          <h3 id="unreviewed-modal-title" className="font-bold text-base">
            Unreviewed AI Content
          </h3>
        </div>
        <p className="text-xs text-slate-600 mb-4">
          This template contains AI-suggested content or placeholders requiring official review before publication.
        </p>
        <div className="p-3 bg-amber-50 rounded-xl border border-amber-200 text-xs text-amber-900 mb-6 max-h-48 overflow-y-auto">
          {items.map((item, idx) => (
            <div key={idx} className="py-1">
              • {item.description || item.label || 'Unreviewed block'}
            </div>
          ))}
        </div>
        <div className="flex items-center justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-xs font-medium text-slate-600 hover:bg-slate-100 rounded-lg"
          >
            Review In Editor
          </button>
          <button
            onClick={onApproveAll}
            disabled={reviewing}
            className="px-4 py-2 text-xs font-semibold text-white bg-brand-600 hover:bg-brand-700 rounded-lg shadow-xs disabled:opacity-50"
          >
            {reviewing ? 'Approving…' : 'Approve All & Continue'}
          </button>
        </div>
      </div>
    </div>
  );
};
