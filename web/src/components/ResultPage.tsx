import React, { useState, useEffect } from 'react';
import { CheckCircle2, Download, FileText, ArrowLeft, ExternalLink, Archive, FileCode, ImageIcon, Loader2 } from 'lucide-react';
import { HomeGenerateResponse, HomeGeneratedDoc } from '../types';

interface ResultPageProps {
  clubId: string | number;
  result: HomeGenerateResponse;
  onEditDetails: () => void;
}

export const ResultPage: React.FC<ResultPageProps> = ({
  result,
  onEditDetails,
}) => {
  const [selectedDocIndex, setSelectedDocIndex] = useState(0);
  const [previewMode, setPreviewMode] = useState<'pdf' | 'image'>('pdf');
  const [pdfBlobUrl, setPdfBlobUrl] = useState<string | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);

  const activeDoc: HomeGeneratedDoc | undefined = result.documents[selectedDocIndex] || result.documents[0];

  useEffect(() => {
    if (!activeDoc) return;
    let active = true;
    setLoadingPreview(true);
    setPreviewError(null);

    // Fetch PDF as Blob with credentials to guarantee cross-browser iframe embedding
    const baseUrl = activeDoc.pdf_url.includes('/download')
      ? activeDoc.pdf_url.replace('/download', '/pdf')
      : activeDoc.pdf_url;
    const sep = baseUrl.includes('?') ? '&' : '?';
    const url = `${baseUrl}${sep}disposition=inline`;
    fetch(url, { credentials: 'include' })
      .then(async (res) => {
        if (!res.ok) {
          throw new Error(`Failed to load PDF (${res.status})`);
        }
        const blob = await res.blob();
        if (!active) return;
        const objectUrl = URL.createObjectURL(blob);
        setPdfBlobUrl((prev) => {
          if (prev) URL.revokeObjectURL(prev);
          return objectUrl;
        });
        setLoadingPreview(false);
      })
      .catch((err) => {
        if (!active) return;
        console.warn('PDF blob loading error, falling back to direct stream:', err);
        setPreviewError(err.message || 'Could not load PDF');
        setLoadingPreview(false);
      });

    return () => {
      active = false;
    };
  }, [activeDoc?.id, activeDoc?.pdf_url]);

  useEffect(() => {
    return () => {
      if (pdfBlobUrl) {
        URL.revokeObjectURL(pdfBlobUrl);
      }
    };
  }, [pdfBlobUrl]);

  return (
    <div className="max-w-6xl mx-auto space-y-6 pb-12">
      {/* Top Banner / Actions Header */}
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-5 sm:p-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <div className="p-3 bg-emerald-100 text-emerald-700 rounded-2xl flex-shrink-0">
            <CheckCircle2 className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[11px] font-bold uppercase tracking-wider text-emerald-800 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                Ready for Signatures
              </span>
              <span className="text-xs text-slate-400">Batch ID: {result.batch_id.slice(0, 8)}</span>
            </div>
            <h1 className="text-lg sm:text-xl font-extrabold text-slate-900 mt-0.5">
              {result.event_title || 'Generated Documents'}
            </h1>
            <p className="text-xs text-slate-500 mt-0.5">
              {result.documents_count} official document{result.documents_count === 1 ? '' : 's'} prepared with unbroken numbering.
            </p>
          </div>
        </div>

        {/* Global Action Buttons */}
        <div className="flex flex-wrap items-center gap-2.5">
          <button
            type="button"
            onClick={onEditDetails}
            className="px-3.5 py-2 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-xl flex items-center gap-1.5 transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            Edit details
          </button>

          {result.zip_url && (
            <a
              href={result.zip_url}
              download
              className="px-4 py-2 text-xs font-bold text-white bg-[#1b365d] hover:bg-[#132742] rounded-xl shadow-sm flex items-center gap-2 transition-colors"
            >
              <Archive className="w-4 h-4" />
              Download All (.zip)
            </a>
          )}
        </div>
      </div>

      {/* Main Grid: Document List on Left, Preview on Right */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Documents Tabs & Quick Actions (4 cols) */}
        <div className="lg:col-span-5 space-y-3">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500 px-1">
            Generated Documents
          </h2>

          {result.documents.map((doc, idx) => {
            const isSelected = selectedDocIndex === idx;
            return (
              <div
                key={doc.id}
                onClick={() => setSelectedDocIndex(idx)}
                className={`p-4 rounded-xl border transition-all cursor-pointer bg-white ${
                  isSelected
                    ? 'border-[#1b365d] ring-1 ring-[#1b365d] shadow-sm'
                    : 'border-slate-200 hover:border-slate-300'
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <FileText className={`w-4 h-4 ${isSelected ? 'text-[#1b365d]' : 'text-slate-400'}`} />
                    <span className="font-bold text-sm text-slate-900">{doc.title}</span>
                  </div>
                  <span className="px-1.5 py-0.5 text-[10px] font-bold bg-slate-100 text-slate-600 rounded">
                    v{doc.version_no}
                  </span>
                </div>

                <div className="mt-2 text-xs font-mono font-bold text-[#1b365d] bg-blue-50/80 px-2 py-1 rounded inline-block border border-blue-100">
                  {doc.ref_no}
                </div>

                {/* Individual Document Download Actions */}
                <div className="mt-3.5 pt-3 border-t border-slate-100 flex items-center gap-2">
                  <a
                    href={doc.pdf_url}
                    download
                    className="flex-1 py-1.5 px-2.5 text-center text-xs font-semibold text-slate-700 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-lg flex items-center justify-center gap-1 transition-colors"
                  >
                    <Download className="w-3.5 h-3.5 text-red-600" />
                    PDF
                  </a>
                  <a
                    href={doc.docx_url}
                    download
                    className="flex-1 py-1.5 px-2.5 text-center text-xs font-semibold text-slate-700 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-lg flex items-center justify-center gap-1 transition-colors"
                  >
                    <FileCode className="w-3.5 h-3.5 text-blue-600" />
                    Word
                  </a>
                  <a
                    href={doc.pdf_url}
                    target="_blank"
                    rel="noreferrer"
                    className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg border border-slate-200"
                    title="Open PDF in new tab"
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                  </a>
                </div>
              </div>
            );
          })}
        </div>

        {/* Right: PDF / Page Preview Panel (7 cols) */}
        <div className="lg:col-span-7">
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden flex flex-col h-[720px]">
            <div className="p-3 border-b border-slate-100 flex flex-wrap items-center justify-between gap-2 bg-slate-50/70">
              <div className="flex items-center gap-2">
                <span className="font-bold text-xs sm:text-sm text-slate-800">
                  {activeDoc?.title}
                </span>
                <span className="text-xs font-mono text-slate-500">
                  ({activeDoc?.ref_no})
                </span>
              </div>

              <div className="flex items-center gap-2">
                {/* View Mode Switcher Pill */}
                <div className="flex items-center bg-slate-200/80 p-0.5 rounded-lg text-xs font-medium">
                  <button
                    type="button"
                    onClick={() => setPreviewMode('pdf')}
                    className={`px-2.5 py-1 rounded-md flex items-center gap-1 transition-all ${
                      previewMode === 'pdf'
                        ? 'bg-white text-slate-900 shadow-sm font-semibold'
                        : 'text-slate-600 hover:text-slate-900'
                    }`}
                  >
                    <FileText className="w-3.5 h-3.5" />
                    PDF
                  </button>
                  <button
                    type="button"
                    onClick={() => setPreviewMode('image')}
                    className={`px-2.5 py-1 rounded-md flex items-center gap-1 transition-all ${
                      previewMode === 'image'
                        ? 'bg-white text-slate-900 shadow-sm font-semibold'
                        : 'text-slate-600 hover:text-slate-900'
                    }`}
                  >
                    <ImageIcon className="w-3.5 h-3.5" />
                    Page View
                  </button>
                </div>

                {activeDoc && (
                  <div className="flex items-center gap-1.5 border-l border-slate-200 pl-2">
                    <a
                      href={`${activeDoc.pdf_url}?disposition=inline`}
                      target="_blank"
                      rel="noreferrer"
                      className="p-1.5 text-slate-500 hover:text-slate-800 hover:bg-slate-200/60 rounded-md transition-colors"
                      title="Open PDF in new tab"
                    >
                      <ExternalLink className="w-3.5 h-3.5" />
                    </a>
                    <a
                      href={activeDoc.pdf_url}
                      download
                      className="px-2.5 py-1 text-xs text-[#1b365d] bg-blue-50 hover:bg-blue-100 rounded-md font-semibold flex items-center gap-1 transition-colors"
                    >
                      <Download className="w-3.5 h-3.5" />
                      Download
                    </a>
                  </div>
                )}
              </div>
            </div>

            {/* Preview Container */}
            <div className="flex-1 bg-slate-100/70 p-3 overflow-auto flex items-center justify-center relative">
              {loadingPreview && (
                <div className="absolute inset-0 bg-white/70 backdrop-blur-xs flex flex-col items-center justify-center z-10 gap-2">
                  <Loader2 className="w-6 h-6 animate-spin text-[#1b365d]" />
                  <span className="text-xs text-slate-500 font-medium">Loading document preview...</span>
                </div>
              )}

              {activeDoc ? (
                previewMode === 'pdf' ? (
                  pdfBlobUrl ? (
                    <iframe
                      src={`${pdfBlobUrl}#toolbar=0`}
                      title={activeDoc.title}
                      className="w-full h-full rounded-xl border border-slate-300 shadow-inner bg-white"
                    />
                  ) : previewError ? (
                    <div className="text-center p-6 bg-white rounded-xl border border-slate-200 shadow-sm max-w-sm">
                      <FileText className="w-10 h-10 text-slate-400 mx-auto mb-2" />
                      <p className="text-sm font-semibold text-slate-800">Browser PDF viewer restricted</p>
                      <p className="text-xs text-slate-500 mt-1 mb-4">
                        Your browser or environment is blocking iframe PDF rendering.
                      </p>
                      <div className="flex flex-col gap-2">
                        <button
                          type="button"
                          onClick={() => setPreviewMode('image')}
                          className="px-3 py-1.5 text-xs font-semibold text-white bg-[#1b365d] hover:bg-[#132742] rounded-lg transition-colors"
                        >
                          Switch to Page View Image
                        </button>
                        <a
                          href={activeDoc.pdf_url.includes('/download') ? activeDoc.pdf_url.replace('/download', '/pdf') + '?disposition=inline' : activeDoc.pdf_url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-xs text-[#1b365d] hover:underline"
                        >
                          Open in external tab &rarr;
                        </a>
                      </div>
                    </div>
                  ) : (
                    <iframe
                      src={`${activeDoc.pdf_url.includes('/download') ? activeDoc.pdf_url.replace('/download', '/pdf') : activeDoc.pdf_url}${activeDoc.pdf_url.includes('?') ? '&' : '?'}disposition=inline#toolbar=0`}
                      title={activeDoc.title}
                      className="w-full h-full rounded-xl border border-slate-300 shadow-inner bg-white"
                    />
                  )
                ) : (
                  <div className="w-full h-full overflow-auto flex flex-col items-center p-2">
                    <img
                      src={activeDoc.preview_url}
                      alt={activeDoc.title}
                      className="max-h-full max-w-full object-contain rounded-lg shadow-md border border-slate-200 bg-white"
                      loading="lazy"
                    />
                  </div>
                )
              ) : (
                <div className="max-w-sm text-center bg-white rounded-xl border border-slate-200 shadow-sm p-8">
                  <FileText className="w-10 h-10 text-slate-300 mx-auto mb-3" />
                  <h3 className="text-sm font-bold text-slate-800">No preview available yet</h3>
                  <p className="text-xs text-slate-500 mt-1">No documents were returned for this request. Go back to edit the document selection and generate again.</p>
                  <button type="button" onClick={onEditDetails} className="mt-4 px-3 py-1.5 text-xs font-semibold text-white bg-[#1b365d] rounded-lg">Edit details</button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
