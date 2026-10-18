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
  CheckCircle2,
  X,
} from 'lucide-react';
import { api } from '../api/client';
import { GeneratedDocument } from '../types';

interface DocumentsTabProps {
  clubId: string | number;
  onViewDocument: (doc: GeneratedDocument) => void;
  onNavigateToEvents?: () => void;
}

export const DocumentsTab: React.FC<DocumentsTabProps> = ({
  clubId,
  onViewDocument: _onViewDocument,
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
      {/* Header Banner */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-slate-900">Documents Library</h1>
            <span className="bg-slate-100 text-slate-700 text-xs px-2.5 py-1 rounded-full font-semibold border border-slate-200">
              {total} Document{total === 1 ? '' : 's'}
            </span>
          </div>
          <p className="text-slate-600 text-sm mt-1">
            Browse, search, sort, and download official generated documents for this club.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={fetchDocuments}
            className="inline-flex items-center gap-1.5 px-3 py-2 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-lg text-xs font-medium text-slate-700 transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          {onNavigateToEvents && (
            <button
              type="button"
              onClick={onNavigateToEvents}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-[#1b365d] hover:bg-[#152a48] text-white rounded-lg text-xs font-semibold shadow-sm transition-colors"
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
              placeholder="Search by title or reference number (e.g., ACM/2026-27/ROOM/001)..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-4 py-2 border border-slate-300 rounded-lg text-xs sm:text-sm focus:outline-none focus:ring-2 focus:ring-[#1b365d] focus:border-transparent"
            />
          </div>
          <button
            type="submit"
            className="w-full sm:w-auto px-4 py-2 bg-[#1b365d] hover:bg-[#152a48] text-white text-xs sm:text-sm font-semibold rounded-lg shadow-sm transition-colors"
          >
            Search
          </button>
          {isFiltered && (
            <button
              type="button"
              onClick={handleClearFilters}
              className="w-full sm:w-auto px-3 py-2 text-xs font-semibold text-slate-600 hover:text-slate-900 border border-slate-200 hover:bg-slate-50 rounded-lg transition-colors"
            >
              Reset Filters
            </button>
          )}
        </form>

        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3 pt-2 border-t border-slate-100 text-xs">
          {/* Template Filter */}
          <div>
            <label className="block text-[11px] font-semibold text-slate-500 mb-1">Type / Template</label>
            <select
              value={selectedTemplate}
              onChange={(e) => {
                setSelectedTemplate(e.target.value);
                setPage(1);
              }}
              className="w-full border border-slate-200 rounded-md py-1.5 px-2 bg-white text-slate-700 focus:outline-none focus:ring-1 focus:ring-[#1b365d]"
            >
              <option value="">All Types</option>
              {templates.map((t) => (
                <option key={t.id} value={t.slug || t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </div>

          {/* Status Filter */}
          <div>
            <label className="block text-[11px] font-semibold text-slate-500 mb-1">Status</label>
            <select
              value={selectedStatus}
              onChange={(e) => {
                setSelectedStatus(e.target.value);
                setPage(1);
              }}
              className="w-full border border-slate-200 rounded-md py-1.5 px-2 bg-white text-slate-700 focus:outline-none focus:ring-1 focus:ring-[#1b365d]"
            >
              <option value="">All Statuses</option>
              <option value="ready">Ready</option>
              <option value="generated">Generated</option>
              <option value="draft">Draft</option>
            </select>
          </div>

          {/* Event Filter */}
          <div>
            <label className="block text-[11px] font-semibold text-slate-500 mb-1">Event</label>
            <select
              value={selectedEventId}
              onChange={(e) => {
                setSelectedEventId(e.target.value);
                setPage(1);
              }}
              className="w-full border border-slate-200 rounded-md py-1.5 px-2 bg-white text-slate-700 focus:outline-none focus:ring-1 focus:ring-[#1b365d]"
            >
              <option value="">All Events</option>
              {eventsList.map((ev) => (
                <option key={ev.id} value={ev.id}>
                  {ev.title}
                </option>
              ))}
            </select>
          </div>

          {/* Date From */}
          <div>
            <label className="block text-[11px] font-semibold text-slate-500 mb-1">Date From</label>
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => {
                setDateFrom(e.target.value);
                setPage(1);
              }}
              className="w-full border border-slate-200 rounded-md py-1 px-2 bg-white text-slate-700 focus:outline-none focus:ring-1 focus:ring-[#1b365d]"
            />
          </div>

          {/* Date To */}
          <div>
            <label className="block text-[11px] font-semibold text-slate-500 mb-1">Date To</label>
            <input
              type="date"
              value={dateTo}
              onChange={(e) => {
                setDateTo(e.target.value);
                setPage(1);
              }}
              className="w-full border border-slate-200 rounded-md py-1 px-2 bg-white text-slate-700 focus:outline-none focus:ring-1 focus:ring-[#1b365d]"
            />
          </div>

          {/* Sort By */}
          <div>
            <label className="block text-[11px] font-semibold text-slate-500 mb-1">Sort By</label>
            <div className="flex gap-1">
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="w-full border border-slate-200 rounded-md py-1.5 px-2 bg-white text-slate-700 focus:outline-none focus:ring-1 focus:ring-[#1b365d]"
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
          <RefreshCw className="w-8 h-8 text-[#1b365d] animate-spin mx-auto mb-3" />
          <p className="text-slate-600 text-sm font-medium">Loading documents library...</p>
        </div>
      ) : error ? (
        <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-center text-red-700 text-sm">
          {error}
        </div>
      ) : documents.length === 0 ? (
        /* Empty State */
        <div className="bg-white rounded-xl border border-slate-200 p-12 text-center shadow-sm">
          <div className="w-16 h-16 bg-blue-50 text-[#1b365d] rounded-full flex items-center justify-center mx-auto mb-4 border border-blue-100">
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
                  className="mt-4 px-4 py-2 bg-[#1b365d] hover:bg-[#152a48] text-white text-xs font-semibold rounded-lg shadow-sm transition-colors"
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
                <tr className="bg-slate-50/80 border-b border-slate-200 text-slate-500 text-[11px] uppercase tracking-wider font-semibold">
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
                        <FileText className="w-4 h-4 text-[#1b365d] flex-shrink-0" />
                        <span>{doc.title}</span>
                      </div>
                      <div className="text-[11px] text-slate-400 mt-0.5">
                        v{doc.current_version_no} • {doc.page_count} page{doc.page_count === 1 ? '' : 's'}
                      </div>
                    </td>

                    {/* Reference No */}
                    <td className="py-3.5 px-4">
                      {doc.ref_no ? (
                        <span className="font-mono text-[11px] font-bold text-amber-900 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded">
                          {doc.ref_no}
                        </span>
                      ) : (
                        <span className="text-slate-400 italic text-xs">Unassigned</span>
                      )}
                    </td>

                    {/* Template Type */}
                    <td className="py-3.5 px-4">
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200">
                        <Tag className="w-3 h-3 text-blue-500" />
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
                      <span
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold border ${
                          doc.status === 'ready' || doc.status === 'generated'
                            ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                            : 'bg-amber-50 text-amber-700 border-amber-200'
                        }`}
                      >
                        <CheckCircle2 className="w-3 h-3" />
                        <span className="capitalize">{doc.status}</span>
                      </span>
                    </td>

                    {/* Actions */}
                    <td className="py-3.5 px-4 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          type="button"
                          onClick={() => handlePreview(doc.id)}
                          title="Preview Document"
                          className="p-1.5 text-slate-600 hover:text-[#1b365d] hover:bg-slate-100 rounded-md transition-colors"
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
                          className="inline-flex items-center gap-1 px-2 py-1 bg-blue-50 hover:bg-blue-100 text-blue-700 border border-blue-200 rounded text-xs font-medium transition-colors"
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
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 max-w-4xl w-full max-h-[90vh] flex flex-col overflow-hidden">
            <div className="p-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
              <div>
                <h3 className="font-bold text-sm sm:text-base text-slate-900">{previewDoc.title}</h3>
                <p className="text-xs text-slate-500 font-mono mt-0.5">
                  Ref: {previewDoc.ref_no || 'Unassigned'} • Version v{previewDoc.current_version_no}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <a
                  href={`/api/v1/clubs/${clubId}/documents/${previewDoc.id}/pdf`}
                  download
                  className="px-3 py-1.5 bg-[#1b365d] text-white text-xs font-bold rounded-lg hover:bg-[#132742] transition-colors flex items-center gap-1.5 shadow-xs"
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
                  onClick={() => setPreviewDoc(null)}
                  className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-200/60 transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>
            <div className="flex-1 bg-slate-100 p-2 overflow-hidden flex items-center justify-center min-h-[500px]">
              <iframe
                src={`/api/v1/clubs/${clubId}/documents/${previewDoc.id}/pdf`}
                className="w-full h-full border-0 rounded-lg shadow-inner bg-white min-h-[500px]"
                title="Document Preview"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
