import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import { ArrowLeft, Download, FileText, History, AlertCircle } from 'lucide-react';

export const DocumentDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { activeClub } = useAuth();

  const [document, setDocument] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!activeClub || !id) return;
    setLoading(true);
    setError(null);
    api.documents.get(activeClub.id, id)
      .then((doc) => {
        setDocument(doc);
      })
      .catch((err: any) => {
        setError(err.message || 'Failed to load document details.');
      })
      .finally(() => setLoading(false));
  }, [activeClub?.id, id]);

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto my-12 text-center text-slate-400 text-xs">
        <div className="h-8 w-8 border-3 border-[#1b365d] border-t-transparent rounded-full animate-spin mx-auto mb-3"></div>
        Loading document details...
      </div>
    );
  }

  if (error || !document) {
    return (
      <div className="max-w-xl mx-auto my-12 p-8 bg-white border border-red-200 rounded-3xl text-center shadow-sm">
        <AlertCircle className="w-10 h-10 text-red-500 mx-auto mb-3" />
        <h2 className="text-base font-bold text-slate-900">Document Not Found</h2>
        <p className="text-xs text-slate-500 mt-1">{error || 'The requested document does not exist or access is restricted.'}</p>
        <button
          type="button"
          onClick={() => navigate('/documents')}
          className="mt-6 px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-semibold rounded-xl"
        >
          Back to Documents
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto my-8 px-4 sm:px-6">
      <button
        type="button"
        onClick={() => navigate('/documents')}
        className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-800 mb-6 transition-colors"
      >
        <ArrowLeft className="w-3.5 h-3.5" />
        <span>Back to My Documents</span>
      </button>

      <div className="bg-white border border-slate-200 rounded-3xl p-6 sm:p-8 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-6 border-b border-slate-100 gap-4">
          <div>
            <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md bg-blue-50 border border-blue-200 text-[#1b365d] text-[11px] font-bold uppercase tracking-wider mb-2">
              <FileText className="w-3 h-3" />
              <span>{document.template_name || 'Document'}</span>
            </div>
            <h1 className="text-xl sm:text-2xl font-bold text-slate-900">{document.title}</h1>
            <p className="text-xs text-slate-500 font-mono mt-1">
              Ref: <span className="text-slate-800 font-semibold">{document.ref_no || 'Pending Allocation'}</span> • v{document.current_version_no}
            </p>
          </div>

          <div className="flex items-center gap-2">
            <a
              href={`/api/v1/clubs/${activeClub?.id}/documents/${document.id}/pdf`}
              download
              className="px-4 py-2 bg-[#1b365d] hover:bg-[#132742] text-white text-xs font-bold rounded-xl transition-colors shadow-sm flex items-center gap-2"
            >
              <Download className="w-4 h-4" />
              <span>PDF</span>
            </a>
            <a
              href={`/api/v1/clubs/${activeClub?.id}/documents/${document.id}/docx`}
              download
              className="px-4 py-2 bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 text-xs font-bold rounded-xl transition-colors shadow-sm flex items-center gap-2"
            >
              <Download className="w-4 h-4" />
              <span>Word (.docx)</span>
            </a>
          </div>
        </div>

        {/* Metadata Details */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 py-6 border-b border-slate-100 text-xs">
          <div>
            <span className="block text-slate-400 font-medium">Status</span>
            <span className="inline-block mt-1 px-2.5 py-0.5 bg-emerald-50 text-emerald-700 border border-emerald-200 font-semibold rounded-md uppercase tracking-wider text-[10px]">
              {document.status}
            </span>
          </div>
          <div>
            <span className="block text-slate-400 font-medium">Created By</span>
            <span className="block font-semibold text-slate-800 mt-1">{document.creator_name || 'Member'}</span>
          </div>
          <div>
            <span className="block text-slate-400 font-medium">Created On</span>
            <span className="block font-semibold text-slate-800 mt-1">
              {new Date(document.created_at).toLocaleDateString()}
            </span>
          </div>
          <div>
            <span className="block text-slate-400 font-medium">Associated Event</span>
            <span className="block font-semibold text-slate-800 mt-1">
              {document.event_name || 'Independent Document'}
            </span>
          </div>
        </div>

        {/* Document Audit / Signatories summary */}
        <div className="pt-6">
          <div className="flex items-center gap-2 mb-4">
            <History className="w-4 h-4 text-slate-400" />
            <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider">Document Information</h3>
          </div>
          <div className="p-4 bg-slate-50 rounded-2xl border border-slate-200 text-xs text-slate-600 space-y-2">
            <p>
              This document was generated under the official authority of <strong>{activeClub?.name}</strong>.
            </p>
            <p className="text-[11px] text-slate-400">
              Download the official formatted PDF for print distribution and institute office submissions, or the Word (.docx) file for custom localized edits.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
