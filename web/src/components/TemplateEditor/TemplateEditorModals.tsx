import React from 'react';
import { Eye, RefreshCw, X, CheckCircle2, AlertCircle } from 'lucide-react';

interface PreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  loading: boolean;
  pages: string[];
}

export const PreviewModal: React.FC<PreviewModalProps> = ({
  isOpen,
  onClose,
  loading,
  pages,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-6">
      <div className="bg-white rounded-xl shadow-2xl max-w-4xl w-full max-h-[90vh] flex flex-col overflow-hidden animate-in fade-in">
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Eye className="w-5 h-5 text-indigo-600" />
            <h3 className="font-bold text-slate-800 text-base">Template Live Preview</h3>
            <span className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded font-mono">
              Dummy Data Render
            </span>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 bg-slate-100 flex flex-col items-center gap-6">
          {loading ? (
            <div className="flex flex-col items-center py-20 text-slate-500">
              <RefreshCw className="w-8 h-8 animate-spin text-indigo-600 mb-3" />
              <p className="text-sm">Generating PDF preview via LibreOffice...</p>
            </div>
          ) : pages.length === 0 ? (
            <div className="p-8 text-center text-slate-500">No preview generated.</div>
          ) : (
            pages.map((pageSrc, idx) => (
              <div
                key={idx}
                className="bg-white shadow-lg border border-slate-300 rounded overflow-hidden max-w-[700px] w-full"
              >
                <img src={pageSrc} alt={`Page ${idx + 1}`} className="w-full h-auto" />
              </div>
            ))
          )}
        </div>

        <div className="px-6 py-3 border-t border-slate-200 flex items-center justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-md"
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-xs p-6">
      <div className="bg-white rounded-xl shadow-xl max-w-xl w-full p-6 animate-in fade-in">
        <div className="flex items-center justify-between pb-3 border-b border-slate-200 mb-4">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-5 h-5 text-emerald-600" />
            <h3 className="font-bold text-slate-800 text-base">Compiler Validation Report</h3>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="text-xs text-slate-600 flex flex-col gap-3 max-h-96 overflow-y-auto">
          <div className="p-3 bg-emerald-50 text-emerald-800 rounded border border-emerald-200 font-medium">
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
            className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-md shadow-xs"
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-6">
      <div className="bg-white rounded-xl shadow-xl max-w-lg w-full p-6 border border-amber-200 animate-in fade-in">
        <div className="flex items-center gap-3 mb-4 text-amber-700">
          <AlertCircle className="w-6 h-6 text-amber-600 shrink-0" />
          <h3 className="font-bold text-base">Unreviewed AI Content</h3>
        </div>
        <p className="text-sm text-slate-600 mb-4">
          This template contains AI-suggested content or placeholders requiring official review before publication.
        </p>
        <div className="p-3 bg-amber-50 rounded border border-amber-200 text-xs text-amber-900 mb-6 max-h-48 overflow-y-auto">
          {items.map((item, idx) => (
            <div key={idx} className="py-1">
              • {item.description || item.label || 'Unreviewed block'}
            </div>
          ))}
        </div>
        <div className="flex items-center justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 rounded-md"
          >
            Review In Editor
          </button>
          <button
            onClick={onApproveAll}
            disabled={reviewing}
            className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-md shadow-xs"
          >
            {reviewing ? 'Reviewing...' : 'Approve & Mark All Reviewed'}
          </button>
        </div>
      </div>
    </div>
  );
};
