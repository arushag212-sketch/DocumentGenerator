import {
  ArrowLeft,
  Download,
  CheckCircle2,
  Calendar,
  Hash,
  Layers,
  FileCheck,
  ShieldCheck,
} from 'lucide-react';
import { GeneratedDocument } from '../types';

interface ReviewDocumentPageProps {
  clubId?: string | number;
  document: GeneratedDocument;
  onBackToDashboard: () => void;
  onEditNewVersion?: () => void;
}

const formatDateDMY = (d: string | Date | undefined) => {
  if (!d) return '—';
  // If already DD/MM/YYYY
  if (typeof d === 'string' && /^\d{2}\/\d{2}\/\d{4}$/.test(d)) return d;
  const dt = new Date(d);
  if (isNaN(dt.getTime())) return String(d);
  const day = String(dt.getDate()).padStart(2, '0');
  const month = String(dt.getMonth() + 1).padStart(2, '0');
  const year = dt.getFullYear();
  return `${day}/${month}/${year}`;
};

export const ReviewDocumentPage: React.FC<ReviewDocumentPageProps> = ({
  document,
  onBackToDashboard,
}) => {
  const displayDate = document.record_snapshot?.document_date
    ? formatDateDMY(document.record_snapshot.document_date)
    : formatDateDMY(document.created_at);

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <button
            onClick={onBackToDashboard}
            type="button"
            className="inline-flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-800 font-semibold mb-2"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            Back to Dashboard
          </button>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-slate-900">{document.title}</h1>
            <span className="bg-emerald-50 text-emerald-700 text-xs px-2.5 py-0.5 rounded-full font-bold border border-emerald-200 uppercase tracking-wider flex items-center gap-1">
              <CheckCircle2 className="w-3 h-3" />
              {document.status}
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-1 text-xs text-slate-600">
            <span className="flex items-center gap-1">
              <Hash className="w-3.5 h-3.5 text-slate-400" />
              Ref: <strong className="font-mono text-slate-800">{document.ref_no || '—'}</strong>
            </span>
            <span className="flex items-center gap-1">
              <Layers className="w-3.5 h-3.5 text-slate-400" />
              Version: <strong className="font-mono text-slate-800">v{document.current_version_no}</strong>
            </span>
            <span className="flex items-center gap-1">
              <Calendar className="w-3.5 h-3.5 text-slate-400" />
              Date: <strong>{displayDate}</strong>
            </span>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-3">
          <a
            href={document.pdf_url}
            download
            className="inline-flex items-center gap-2 bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-lg text-xs sm:text-sm font-bold shadow-sm transition-colors"
          >
            <Download className="w-4 h-4" />
            Download PDF
          </a>

          <a
            href={document.docx_url}
            download
            className="inline-flex items-center gap-2 bg-[#1b365d] hover:bg-[#152a48] text-white px-4 py-2 rounded-lg text-xs sm:text-sm font-bold shadow-sm transition-colors"
          >
            <Download className="w-4 h-4" />
            Download DOCX
          </a>
        </div>
      </div>

      {/* Main Review Section: PDF Previews (Center) + Meta / Versions (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* PDF Previews Canvas */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-slate-200/70 rounded-xl p-6 border border-slate-300 shadow-inner space-y-6">
            <div className="flex items-center justify-between text-xs text-slate-600 px-1">
              <span className="font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                <FileCheck className="w-4 h-4 text-emerald-700" />
                Rendered PDF Preview ({document.page_images.length} {document.page_images.length === 1 ? 'Page' : 'Pages'})
              </span>
              <span className="text-[11px] text-slate-500 font-mono">150 DPI Rasterized</span>
            </div>

            {document.page_images.map((imgUrl, idx) => (
              <div key={idx} className="space-y-2">
                <div className="flex items-center justify-between text-xs text-slate-500 px-2 font-mono">
                  <span>Page {idx + 1} of {document.page_images.length}</span>
                </div>
                <div className="bg-white rounded-lg shadow-lg border border-slate-300 overflow-hidden">
                  <img
                    src={imgUrl}
                    alt={`Document Page ${idx + 1}`}
                    className="w-full h-auto object-contain block select-none"
                    loading="lazy"
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Side Details & Version History */}
        <div className="space-y-5">
          {/* Metadata Card */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5 space-y-3">
            <h3 className="font-bold text-slate-900 text-sm border-b border-slate-100 pb-2">
              Document Information
            </h3>
            <div className="text-xs space-y-2 text-slate-600">
              <div className="flex justify-between">
                <span className="text-slate-400">Template</span>
                <span className="font-semibold text-slate-800 capitalize">{document.template_id.replace(/_/g, ' ')}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Reference No.</span>
                <span className="font-mono font-semibold text-amber-800">{document.ref_no || '—'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Total Pages</span>
                <span className="font-semibold text-slate-800">{document.page_images.length} Pages</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">PDF Converter</span>
                <span className="font-semibold text-slate-800">LibreOffice (Official)</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Security</span>
                <span className="text-emerald-700 font-semibold flex items-center gap-1">
                  <ShieldCheck className="w-3.5 h-3.5" />
                  Audit Logged
                </span>
              </div>
            </div>
          </div>

          {/* Version History Card */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5 space-y-3">
            <h3 className="font-bold text-slate-900 text-sm border-b border-slate-100 pb-2 flex items-center justify-between">
              <span>Version History</span>
              <span className="text-[10px] text-slate-400 font-mono">Immutable Revisions</span>
            </h3>

            <div className="space-y-2">
              {document.versions.map((v) => (
                <div
                  key={v.id}
                  className="p-3 bg-slate-50 rounded-lg border border-slate-200 text-xs flex items-center justify-between"
                >
                  <div>
                    <div className="flex items-center gap-1.5">
                      <span className="font-mono font-bold text-[#1b365d]">v{v.version_no}</span>
                      <span className="text-[10px] bg-slate-200 text-slate-700 px-1.5 py-0.2 rounded font-semibold">
                        Generated
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-500 mt-0.5">
                      {new Date(v.created_at).toLocaleString()}
                    </p>
                  </div>
                  <div className="flex items-center gap-1">
                    <a
                      href={document.pdf_url}
                      download
                      className="p-1.5 text-slate-500 hover:text-red-600 rounded hover:bg-slate-200"
                      title="Download PDF"
                    >
                      <Download className="w-3.5 h-3.5" />
                    </a>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
