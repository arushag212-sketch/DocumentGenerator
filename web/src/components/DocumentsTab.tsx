import React, { useState, useEffect } from 'react';
import {
  FileText,
  Search,
  Download,
  Eye,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
  FolderOpen,
  ArrowUpDown,
  Tag,
  X,
} from 'lucide-react';
import { StatusBadge } from '../pages/DocumentDetailPage';
import { api } from '../api/client';
import { GeneratedDocument } from '../types';

interface DocumentsTabProps {
  clubId: string | number;
  onViewDocument: (doc: GeneratedDocument) => void;
  onNavigateToEvents?: () => void;
}

export const DocumentsTab: React.FC<DocumentsTabProps> = ({
  clubId,
  onViewDocument,
  onNavigateToEvents,
}) => {
  const [documents, setDocuments] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [previewDoc, setPreviewDoc] = useState<any | null>(null);
  const [pdfBlobUrl, setPdfBlobUrl] = useState<string | null>(null);
  const [loadingPdf, setLoadingPdf] = useState(false);
  const [previewMode, setPreviewMode] = useState<'pdf' | 'image'>('pdf');

  // Filters & Search
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedTemplate, setSelectedTemplate] = useState('');
  const [selectedStatus, setSelectedStatus] = useState('');
  const [selectedEventId, setSelectedEventId] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [sortBy, setSortBy] = useState('created_at');
  const [sortOrder, setSortOrder] = useState('desc');

  // Metadata dropdowns
  const [templates, setTemplates] = useState<any[]>([]);
  const [eventsList, setEventsList] = useState<any[]>([]);

  useEffect(() => {
    // Load available templates & events for filter dropdowns
    api.documents.listTemplates(clubId).then((res) => setTemplates(res || [])).catch(() => {});
    api.events.list(clubId).then((res) => setEventsList(res.items || [])).catch(() => {});
  }, [clubId]);

  const fetchDocuments = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.documents.list(clubId, {
        q: searchQuery,
        template_id: selectedTemplate,
        status: selectedStatus,
        event_id: selectedEventId,
        date_from: dateFrom,
        date_to: dateTo,
        sort_by: sortBy,
        sort_order: sortOrder,
        page,
        page_size: pageSize,
      });
      setDocuments(res.items || []);
      setTotal(res.total || 0);
      setTotalPages(res.total_pages || 1);
    } catch (err: any) {
      setError(err.message || 'Failed to load documents');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDocuments();
  }, [
    clubId,
    page,
    pageSize,
    selectedTemplate,
    selectedStatus,
    selectedEventId,
    dateFrom,
    dateTo,
    sortBy,
    sortOrder,
  ]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchDocuments();
  };

  const handleClearFilters = () => {
    setSearchQuery('');
    setSelectedTemplate('');
    setSelectedStatus('');
    setSelectedEventId('');
    setDateFrom('');
    setDateTo('');
    setSortBy('created_at');
    setSortOrder('desc');
    setPage(1);
  };

  useEffect(() => {
    if (!previewDoc) {
      if (pdfBlobUrl) URL.revokeObjectURL(pdfBlobUrl);
      setPdfBlobUrl(null);
      setPreviewMode('pdf');
      return;
    }
    let active = true;
    setLoadingPdf(true);
    setPreviewMode('pdf');
    const pdfUrl = `/api/v1/clubs/${clubId}/documents/${previewDoc.id}/pdf?disposition=inline`;
    fetch(pdfUrl, { credentials: 'include' })
      .then(async (res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const blob = await res.blob();
        if (!active) return;
        const objUrl = URL.createObjectURL(blob);
        setPdfBlobUrl(objUrl);
      })
      .catch((err) => {
        console.warn('PDF blob loading error, falling back to image preview:', err);
        if (active) setPreviewMode('image');
      })
      .finally(() => {
        if (active) setLoadingPdf(false);
      });

    return () => {
      active = false;
    };
  }, [previewDoc?.id, clubId]);

  const handlePreview = async (docId: string) => {
    try {
      const doc = await api.documents.get(clubId, docId);
      setPreviewDoc(doc);
    } catch (err: any) {
      alert(`Could not open document preview: ${err.message}`);
    }
  };

  const isFiltered =
    Boolean(searchQuery) ||
    Boolean(selectedTemplate) ||
    Boolean(selectedStatus) ||
    Boolean(selectedEventId) ||
    Boolean(dateFrom) ||
    Boolean(dateTo);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h1 className="page-title">Documents</h1>
          <p className="page-subtitle">
            {total} document{total === 1 ? '' : 's'} generated by this club. Search by title or reference number.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={fetchDocuments}
            className="btn-ghost"
            aria-label="Refresh"
            title="Refresh"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
          {onNavigateToEvents && (
            <button
              type="button"
              onClick={onNavigateToEvents}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-brand-700 hover:bg-brand-800 text-white rounded-lg text-xs font-semibold shadow-sm transition-colors"
            >
              <FolderOpen className="w-3.5 h-3.5" />
              Event Workflows
            </button>
          )}
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4 space-y-4">
        <form onSubmit={handleSearchSubmit} className="flex flex-col sm:flex-row items-center gap-3">
          <div className="relative flex-1 w-full">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search by title or reference number …"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-4 py-2 border border-slate-300 rounded-lg text-xs sm:text-sm focus:outline-none focus:ring-2 focus:ring-brand-700 focus:border-transparent"
            />
          </div>
          <button
            type="submit"
            className="w-full sm:w-auto px-4 py-2 bg-brand-700 hover:bg-brand-800 text-white text-xs sm:text-sm font-semibold rounded-lg shadow-sm transition-colors"
          >
            Search
          </button>
          {isFiltered && (
            <button
              type="button"
              onClick={handleClearFilters}
              className="w-full sm:w-auto px-3 py-2 text-xs font-semibold text-slate-600 hover:text-slate-900 border border-slate-200 hover:bg-slate-50 rounded-lg transition-colors"
            >
              Clear filters
            </button>
          )}
        </form>

        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3 pt-2 border-t border-slate-100 text-xs">
          {/* Template Filter */}
          <div>
            <label className="block text-xs font-semibold text-slate-500 mb-1">Type / Template</label>
            <select
              value={selectedTemplate}
              onChange={(e) => {
                setSelectedTemplate(e.target.value);
                setPage(1);
              }}
              className="w-full border border-slate-200 rounded-md py-1.5 px-2 bg-white text-slate-700 focus:outline-none focus:ring-1 focus:ring-brand-700"
            >
              <option value="">All types</option>
              {templates.map((t) => (
                <option key={t.id} value={t.slug || t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </div>

          {/* Status Filter */}
          <div>
            <label className="block text-xs font-semibold text-slate-500 mb-1">Status</label>
            <select
              value={selectedStatus}
              onChange={(e) => {
                setSelectedStatus(e.target.value);
                setPage(1);
              }}
              className="w-full border border-slate-200 rounded-md py-1.5 px-2 bg-white text-slate-700 focus:outline-none focus:ring-1 focus:ring-brand-700"
            >
              <option value="">All statuses</option>
              <option value="ready">Ready</option>
              <option value="submitted">Awaiting review</option>
              <option value="changes_requested">Changes requested</option>
              <option value="approved">Approved</option>
            </select>
          </div>

          {/* Event Filter */}
          <div>
            <label className="block text-xs font-semibold text-slate-500 mb-1">Event</label>
            <select
              value={selectedEventId}
              onChange={(e) => {
                setSelectedEventId(e.target.value);
                setPage(1);
              }}
              className="w-full border border-slate-200 rounded-md py-1.5 px-2 bg-white text-slate-700 focus:outline-none focus:ring-1 focus:ring-brand-700"
            >
              <option value="">All events</option>
              {eventsList.map((ev) => (
                <option key={ev.id} value={ev.id}>
                  {ev.title}
                </option>
              ))}
            </select>
          </div>

          {/* Date From */}
          <div>
            <label className="block text-xs font-semibold text-slate-500 mb-1">Date From</label>
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => {
                setDateFrom(e.target.value);
                setPage(1);
              }}
              className="w-full border border-slate-200 rounded-md py-1 px-2 bg-white text-slate-700 focus:outline-none focus:ring-1 focus:ring-brand-700"
            />
          </div>

          {/* Date To */}
          <div>
            <label className="block text-xs font-semibold text-slate-500 mb-1">Date To</label>
            <input
              type="date"
              value={dateTo}
              onChange={(e) => {
                setDateTo(e.target.value);
                setPage(1);
              }}
              className="w-full border border-slate-200 rounded-md py-1 px-2 bg-white text-slate-700 focus:outline-none focus:ring-1 focus:ring-brand-700"
            />
          </div>

          {/* Sort By */}
          <div>
            <label className="block text-xs font-semibold text-slate-500 mb-1">Sort By</label>
            <div className="flex gap-1">
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="w-full border border-slate-200 rounded-md py-1.5 px-2 bg-white text-slate-700 focus:outline-none focus:ring-1 focus:ring-brand-700"
              >
                <option value="created_at">Date</option>
                <option value="title">Title</option>
                <option value="ref_no">Ref No</option>
                <option value="status">Status</option>
              </select>
              <button
                type="button"
                onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
                className="px-2 border border-slate-200 rounded-md bg-slate-50 hover:bg-slate-100 text-slate-600"
                title={`Sort ${sortOrder === 'asc' ? 'Descending' : 'Ascending'}`}
              >
                <ArrowUpDown className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Main Documents Content */}
      {loading ? (
        <div className="bg-white rounded-xl border border-slate-200 p-12 text-center shadow-sm">
          <RefreshCw className="w-8 h-8 text-brand-700 animate-spin mx-auto mb-3" />
          <p className="text-slate-600 text-sm font-medium">Loading documents library...</p>
        </div>
      ) : error ? (
        <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-center text-red-700 text-sm">
          {error}
        </div>
      ) : documents.length === 0 ? (
        /* Empty State */
        <div className="bg-white rounded-xl border border-slate-200 p-12 text-center shadow-sm">
          <div className="w-16 h-16 bg-brand-50 text-brand-700 rounded-full flex items-center justify-center mx-auto mb-4 border border-brand-100">
            <FileText className="w-8 h-8" />
          </div>
          {isFiltered ? (
            <>
              <h3 className="text-lg font-bold text-slate-800">No matching documents found</h3>
              <p className="text-slate-500 text-xs sm:text-sm mt-1 max-w-md mx-auto">
                No documents matched your active filters or search terms. Try adjusting your search query or resetting filters.
              </p>
              <button
                type="button"
                onClick={handleClearFilters}
                className="mt-4 px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-lg transition-colors"
              >
                Clear All Filters
              </button>
            </>
          ) : (
            <>
              <h3 className="text-lg font-bold text-slate-800">No documents generated yet</h3>
              <p className="text-slate-500 text-xs sm:text-sm mt-1 max-w-md mx-auto">
                You haven't generated any documents for this club yet. Use the "Describe your event" flow in Events to batch generate packages or pick a template from the Template Gallery.
              </p>
              {onNavigateToEvents && (
                <button
                  type="button"
                  onClick={onNavigateToEvents}
                  className="mt-4 px-4 py-2 bg-brand-700 hover:bg-brand-800 text-white text-xs font-semibold rounded-lg shadow-sm transition-colors"
                >
                  Start Event Workflow
                </button>
              )}
            </>
          )}
        </div>
      ) : (
        /* Documents Table */
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs sm:text-sm">
              <thead>
                <tr className="bg-slate-50/80 border-b border-slate-200 text-slate-500 text-xs font-semibold">
                  <th className="py-3 px-4">Document Title</th>
                  <th className="py-3 px-4">Reference No</th>
                  <th className="py-3 px-4">Template Type</th>
                  <th className="py-3 px-4">Linked Event</th>
                  <th className="py-3 px-4">Created Date</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4 text-right">Downloads & Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {documents.map((doc) => (
                  <tr key={doc.id} className="hover:bg-slate-50/60 transition-colors">
                    {/* Document Title & Pages */}
                    <td className="py-3.5 px-4">
                      <div className="font-semibold text-slate-900 flex items-center gap-1.5">
                        <FileText className="w-4 h-4 text-brand-700 flex-shrink-0" />
                        <span>{doc.title}</span>
                      </div>
                      <div className="text-xs text-slate-400 mt-0.5">
                        v{doc.current_version_no} • {doc.page_count} page{doc.page_count === 1 ? '' : 's'}
                      </div>
                    </td>

                    {/* Reference No */}
                    <td className="py-3.5 px-4">
                      {doc.ref_no ? (
                        <span className="font-mono text-xs font-bold text-amber-900 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded">
                          {doc.ref_no}
                        </span>
                      ) : (
                        <span className="text-slate-400 italic text-xs">Unassigned</span>
                      )}
                    </td>

                    {/* Template Type */}
                    <td className="py-3.5 px-4">
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-brand-50 text-brand-700 border border-brand-200">
                        <Tag className="w-3 h-3 text-brand-500" />
                        {doc.template_name || doc.template_slug}
                      </span>
                    </td>

                    {/* Linked Event */}
                    <td className="py-3.5 px-4">
                      {doc.event_title ? (
                        <span className="text-slate-700 font-medium text-xs">
                          {doc.event_title}
                        </span>
                      ) : (
                        <span className="text-slate-400 text-xs italic">—</span>
                      )}
                    </td>

                    {/* Created Date */}
                    <td className="py-3.5 px-4 text-slate-600 text-xs">
                      {doc.created_at ? new Date(doc.created_at).toLocaleDateString('en-GB') : '—'}
                    </td>

                    {/* Status Badge */}
                    <td className="py-3.5 px-4">
                      <StatusBadge status={doc.status} />
                    </td>

                    {/* Actions */}
                    <td className="py-3.5 px-4 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          type="button"
                          onClick={() => handlePreview(doc.id)}
                          title="Preview Document"
                          className="p-1.5 text-slate-600 hover:text-brand-700 hover:bg-slate-100 rounded-md transition-colors"
                        >
                          <Eye className="w-4 h-4" />
                        </button>

                        <a
                          href={doc.pdf_url}
                          download
                          title="Download PDF"
                          className="inline-flex items-center gap-1 px-2 py-1 bg-red-50 hover:bg-red-100 text-red-700 border border-red-200 rounded text-xs font-medium transition-colors"
                        >
                          <Download className="w-3 h-3" />
                          PDF
                        </a>

                        <a
                          href={doc.docx_url}
                          download
                          title="Download Editable DOCX"
                          className="inline-flex items-center gap-1 px-2 py-1 bg-brand-50 hover:bg-brand-100 text-brand-700 border border-brand-200 rounded text-xs font-medium transition-colors"
                        >
                          <Download className="w-3 h-3" />
                          DOCX
                        </a>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination Footer */}
          <div className="p-4 border-t border-slate-200 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-slate-600 bg-slate-50/50">
            <div className="flex items-center gap-2">
              <span>Rows per page:</span>
              <select
                value={pageSize}
                onChange={(e) => {
                  setPageSize(Number(e.target.value));
                  setPage(1);
                }}
                className="border border-slate-200 rounded py-1 px-2 bg-white text-slate-700 focus:outline-none"
              >
                <option value={10}>10</option>
                <option value={25}>25</option>
                <option value={50}>50</option>
              </select>
              <span>
                Showing {Math.min((page - 1) * pageSize + 1, total)} to {Math.min(page * pageSize, total)} of {total} documents
              </span>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => setPage(page - 1)}
                className="p-1.5 border border-slate-200 rounded bg-white hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed text-slate-700"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <span className="font-semibold px-2">
                Page {page} of {totalPages}
              </span>
              <button
                type="button"
                disabled={page >= totalPages}
                onClick={() => setPage(page + 1)}
                className="p-1.5 border border-slate-200 rounded bg-white hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed text-slate-700"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* DOCUMENT PREVIEW MODAL */}
      {previewDoc && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs z-50 flex items-center justify-center p-3 sm:p-6 animate-in fade-in">
          <div className="bg-white rounded-xl shadow-2xl border border-slate-200 max-w-4xl w-full max-h-[92vh] flex flex-col overflow-hidden">
            <div className="p-4 border-b border-slate-200 flex flex-wrap items-center justify-between bg-slate-50 gap-3">
              <div>
                <h3 className="font-bold text-sm sm:text-base text-slate-900">{previewDoc.title}</h3>
                <p className="text-xs text-slate-500 font-mono mt-0.5">
                  Ref: {previewDoc.ref_no || 'Unassigned'} • Version v{previewDoc.current_version_no}
                </p>
              </div>

              {/* View toggle */}
              <div className="flex items-center gap-1 bg-slate-200/80 p-0.5 rounded-lg text-xs font-semibold">
                <button
                  type="button"
                  onClick={() => setPreviewMode('pdf')}
                  className={`px-2.5 py-1 rounded-md transition ${previewMode === 'pdf' ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-600 hover:text-slate-900'}`}
                >
                  PDF Document
                </button>
                <button
                  type="button"
                  onClick={() => setPreviewMode('image')}
                  className={`px-2.5 py-1 rounded-md transition ${previewMode === 'image' ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-600 hover:text-slate-900'}`}
                >
                  Page View
                </button>
              </div>

              <div className="flex items-center gap-2">
                <a
                  href={`/api/v1/clubs/${clubId}/documents/${previewDoc.id}/pdf`}
                  download
                  className="px-3 py-1.5 bg-brand-700 text-white text-xs font-bold rounded-lg hover:bg-brand-800 transition-colors flex items-center gap-1.5 shadow-xs"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Download PDF</span>
                </a>
                <a
                  href={`/api/v1/clubs/${clubId}/documents/${previewDoc.id}/docx`}
                  download
                  className="px-3 py-1.5 bg-white text-slate-700 text-xs font-bold rounded-lg hover:bg-slate-100 transition-colors flex items-center gap-1.5 border border-slate-300"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Word (.docx)</span>
                </a>
                <button
                  type="button"
                  onClick={() => {
                    setPreviewDoc(null);
                    if (onViewDocument) onViewDocument(previewDoc);
                  }}
                  className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-lg transition-colors"
                >
                  Details
                </button>
                <button
                  type="button"
                  onClick={() => setPreviewDoc(null)}
                  className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-200/60 transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            <div className="flex-1 bg-slate-100 p-2 sm:p-4 overflow-auto flex items-center justify-center min-h-[500px]">
              {loadingPdf && previewMode === 'pdf' ? (
                <div className="text-center py-12">
                  <div className="w-8 h-8 border-3 border-brand-700 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
                  <p className="text-xs text-slate-500 font-medium">Loading PDF document...</p>
                </div>
              ) : previewMode === 'pdf' && pdfBlobUrl ? (
                <iframe
                  src={`${pdfBlobUrl}#toolbar=0`}
                  className="w-full h-full border-0 rounded-xl shadow-md bg-white min-h-[550px]"
                  title="Document Preview"
                />
              ) : (
                <div className="flex flex-col items-center justify-center max-w-full">
                  <img
                    src={`/api/v1/clubs/${clubId}/documents/${previewDoc.id}/preview`}
                    alt="Document page preview"
                    className="max-h-[75vh] w-auto max-w-full object-contain rounded-xl shadow-lg border border-slate-300 bg-white"
                    onError={(e) => {
                      (e.target as HTMLElement).style.display = 'none';
                    }}
                  />
                  <div className="mt-3 text-center">
                    <button
                      type="button"
                      onClick={() => setPreviewMode('pdf')}
                      className="text-xs text-brand-700 hover:underline font-semibold"
                    >
                      Switch back to interactive PDF viewer
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
