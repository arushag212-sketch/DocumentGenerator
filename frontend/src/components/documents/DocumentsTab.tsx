import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { notify } from '../common/Toaster';
import {
  FileText,
  Search,
  Download,
  Eye,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
  ArrowUpDown,
  X,
  Trash2,
  MoreHorizontal,
  Plus,
  SlidersHorizontal,
  CopyPlus,
} from 'lucide-react';
import { StatusBadge } from '../../pages/DocumentDetailPage';
import { api } from '../../api/client';
import { GeneratedDocument } from '../../types';
import { DeleteDocsDialog, TrashDialog, isDeletable } from './DocumentTrash';

interface DocumentsTabProps {
  clubId: string | number;
  onViewDocument: (doc: GeneratedDocument) => void;
  onNavigateToEvents?: () => void;
  /** Opened from "Send a document for review": list ready documents and open them at the review box */
  reviewMode?: boolean;
  /** Status filter to start with, e.g. from /documents?status=submitted */
  initialStatus?: string;
}

const menuItem = 'flex w-full items-center gap-2.5 px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50';

export const DocumentsTab: React.FC<DocumentsTabProps> = ({
  clubId,
  onViewDocument,
  onNavigateToEvents,
  reviewMode = false,
  initialStatus = '',
}) => {
  const docLink = (id: string) => `/documents/${id}${reviewMode ? '?review=1' : ''}`;
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
  // Delete / Trash
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [toDelete, setToDelete] = useState<any[] | null>(null);
  const [trashOpen, setTrashOpen] = useState(false);
  const [menuFor, setMenuFor] = useState<string | null>(null);
  const navigate = useNavigate();
  const duplicate = async (doc: any) => {
    try {
      const res = await api.documents.duplicate(clubId, doc.id);
      notify('Copy created. Change the date and details for the new event.', 'success');
      navigate(`/documents/${res.id}`);
    } catch (err: any) {
      notify(err.message || 'Could not duplicate the document.', 'error');
    }
  };
  const [showFilters, setShowFilters] = useState(false);

  // Filters & Search
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedTemplate, setSelectedTemplate] = useState('');
  const [selectedStatus, setSelectedStatus] = useState(reviewMode ? 'ready' : initialStatus);
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
      setSelectedIds(new Set());
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

  useEffect(() => {
    if (!menuFor) return;
    const close = () => setMenuFor(null);
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && close();
    window.addEventListener('mousedown', close);
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('mousedown', close);
      window.removeEventListener('keydown', onKey);
    };
  }, [menuFor]);

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
      notify(`Could not open the preview: ${err.message}`, 'error');
    }
  };

  const isFiltered =
    Boolean(searchQuery) ||
    Boolean(selectedTemplate) ||
    Boolean(selectedStatus) ||
    Boolean(selectedEventId) ||
    Boolean(dateFrom) ||
    Boolean(dateTo);

  const STATUS_TABS: { value: string; label: string }[] = [
    { value: '', label: 'All' },
    { value: 'ready', label: 'Ready' },
    { value: 'submitted', label: 'Awaiting review' },
    { value: 'changes_requested', label: 'Changes requested' },
    { value: 'approved', label: 'Approved' },
  ];
  const advancedFilterCount = [selectedTemplate, selectedEventId, dateFrom, dateTo].filter(Boolean).length;
  const deletableOnPage = documents.filter((d) => isDeletable(d.status));
  const allOnPageSelected = deletableOnPage.length > 0 && deletableOnPage.every((d) => selectedIds.has(d.id));
  const toggleOne = (id: string, on: boolean) =>
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (on) next.add(id);
      else next.delete(id);
      return next;
    });
  const fmtDate = (v?: string) => (v ? new Date(v).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }) : '—');

  const rowMenu = (doc: any) => (
    <div className="relative" onMouseDown={(e) => e.stopPropagation()}>
      <button
        type="button"
        className="btn-icon"
        aria-label={`More actions for ${doc.title}`}
        aria-haspopup="menu"
        aria-expanded={menuFor === doc.id}
        onClick={() => setMenuFor(menuFor === doc.id ? null : doc.id)}
      >
        <MoreHorizontal className="w-4 h-4" />
      </button>
      {menuFor === doc.id && (
        <div role="menu" className="absolute right-0 top-full z-30 mt-1 w-48 rounded-lg border border-slate-200 bg-white py-1 shadow-popover">
          <button type="button" role="menuitem" className={menuItem} onClick={() => { setMenuFor(null); handlePreview(doc.id); }}>
            <Eye className="w-4 h-4 text-slate-400" /> Preview
          </button>
          <a role="menuitem" className={menuItem} href={doc.pdf_url} download onClick={() => setMenuFor(null)}>
            <Download className="w-4 h-4 text-slate-400" /> Download PDF
          </a>
          <a role="menuitem" className={menuItem} href={doc.docx_url} download onClick={() => setMenuFor(null)}>
            <Download className="w-4 h-4 text-slate-400" /> Download Word
          </a>
          <button type="button" role="menuitem" className={menuItem} onClick={() => { setMenuFor(null); duplicate(doc); }}>
            <CopyPlus className="w-4 h-4 text-slate-400" /> Duplicate for next event
          </button>
          {isDeletable(doc.status) && (
            <>
              <div className="my-1 border-t border-slate-100" />
              <button
                type="button"
                role="menuitem"
                className={`${menuItem} text-red-600 hover:bg-red-50`}
                onClick={() => { setMenuFor(null); setToDelete([doc]); }}
              >
                <Trash2 className="w-4 h-4" /> Delete
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );

  return (
    <div>
      {/* Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Documents</h1>
          <p className="page-subtitle">
            {total} document{total === 1 ? '' : 's'} in this club
          </p>
          {reviewMode && (
            <p className="mt-3 rounded-lg bg-brand-50 px-3 py-2 text-sm text-brand-800">
              Showing documents that are ready. Choose the one you want to send for review, then click{' '}
              <strong>Submit for review</strong> on its page.
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button type="button" onClick={fetchDocuments} className="btn-icon" aria-label="Refresh" title="Refresh">
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
          <button
            type="button"
            onClick={() => setTrashOpen(true)}
            className="btn-secondary"
            title="Deleted documents (restorable for 30 days)"
          >
            <Trash2 className="w-4 h-4" />
            Trash
          </button>
          {onNavigateToEvents && (
            <button type="button" onClick={onNavigateToEvents} className="btn-primary">
              <Plus className="w-4 h-4" />
              Create documents
            </button>
          )}
        </div>
      </div>

      {/* Toolbar: search, status tabs, more filters */}
      <div className="surface-card mb-4">
        <div className="flex flex-col gap-3 p-3 sm:flex-row sm:items-center">
          <form onSubmit={handleSearchSubmit} className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              type="search"
              placeholder="Search by title or reference number"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="input-field pl-9"
              aria-label="Search documents"
            />
          </form>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setShowFilters((v) => !v)}
              className={`btn-secondary ${showFilters || advancedFilterCount ? 'border-brand-300 text-brand-700' : ''}`}
              aria-expanded={showFilters}
            >
              <SlidersHorizontal className="w-4 h-4" />
              Filters
              {advancedFilterCount > 0 && (
                <span className="rounded-full bg-brand-700 px-1.5 text-[11px] font-semibold text-white">{advancedFilterCount}</span>
              )}
            </button>
            <div className="flex items-center gap-1">
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="input-field w-auto pr-8"
                aria-label="Sort by"
              >
                <option value="created_at">Newest</option>
                <option value="title">Title</option>
                <option value="ref_no">Reference</option>
                <option value="status">Status</option>
              </select>
              <button
                type="button"
                onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
                className="btn-icon"
                title={sortOrder === 'asc' ? 'Ascending' : 'Descending'}
                aria-label={`Sort ${sortOrder === 'asc' ? 'descending' : 'ascending'}`}
              >
                <ArrowUpDown className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>

        <div className="flex gap-1 overflow-x-auto border-t border-slate-100 px-3 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden" role="tablist" aria-label="Filter by status">
          {STATUS_TABS.map((t) => {
            const active = selectedStatus === t.value;
            return (
              <button
                key={t.value || 'all'}
                type="button"
                role="tab"
                aria-selected={active}
                onClick={() => {
                  setSelectedStatus(t.value);
                  setPage(1);
                }}
                className={`relative whitespace-nowrap px-3 py-2.5 text-sm font-medium transition-colors ${
                  active ? 'text-brand-700' : 'text-slate-500 hover:text-slate-800'
                }`}
              >
                {t.label}
                {active && <span className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-brand-700" />}
              </button>
            );
          })}
        </div>

        {showFilters && (
          <div className="grid grid-cols-1 gap-3 border-t border-slate-100 p-3 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <label className="field-label text-xs" htmlFor="flt-type">Document type</label>
              <select
                id="flt-type"
                value={selectedTemplate}
                onChange={(e) => {
                  setSelectedTemplate(e.target.value);
                  setPage(1);
                }}
                className="input-field"
              >
                <option value="">All types</option>
                {templates.map((t) => (
                  <option key={t.id} value={t.slug || t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="field-label text-xs" htmlFor="flt-event">Event</label>
              <select
                id="flt-event"
                value={selectedEventId}
                onChange={(e) => {
                  setSelectedEventId(e.target.value);
                  setPage(1);
                }}
                className="input-field"
              >
                <option value="">All events</option>
                {eventsList.map((ev) => (
                  <option key={ev.id} value={ev.id}>
                    {ev.title}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="field-label text-xs" htmlFor="flt-from">Created from</label>
              <input
                id="flt-from"
                type="date"
                value={dateFrom}
                onChange={(e) => {
                  setDateFrom(e.target.value);
                  setPage(1);
                }}
                className="input-field"
              />
            </div>
            <div>
              <label className="field-label text-xs" htmlFor="flt-to">Created to</label>
              <input
                id="flt-to"
                type="date"
                value={dateTo}
                onChange={(e) => {
                  setDateTo(e.target.value);
                  setPage(1);
                }}
                className="input-field"
              />
            </div>
            {isFiltered && (
              <div className="sm:col-span-2 lg:col-span-4">
                <button type="button" onClick={handleClearFilters} className="btn-ghost btn-sm">
                  <X className="w-3.5 h-3.5" /> Clear all filters
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Main Documents Content */}
      {loading ? (
        <div className="surface-card divide-y divide-slate-100" aria-busy="true" aria-label="Loading documents">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="flex items-center gap-4 px-4 py-4">
              <div className="skeleton h-9 w-9 rounded-lg" />
              <div className="flex-1 space-y-2">
                <div className="skeleton h-3.5 w-2/5" />
                <div className="skeleton h-3 w-1/4" />
              </div>
              <div className="skeleton hidden h-5 w-20 rounded-full sm:block" />
            </div>
          ))}
        </div>
      ) : error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center text-sm text-red-700">{error}</div>
      ) : documents.length === 0 ? (
        /* Empty State */
        <div className="surface-card px-6 py-16 text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-brand-50 text-brand-700">
            <FileText className="h-6 w-6" />
          </div>
          {isFiltered ? (
            <>
              <h3 className="text-base font-semibold text-slate-900">No matching documents</h3>
              <p className="mx-auto mt-1 max-w-sm text-sm text-slate-500">Try a different search, or clear the filters.</p>
              <button type="button" onClick={handleClearFilters} className="btn-secondary mt-5">
                Clear filters
              </button>
            </>
          ) : (
            <>
              <h3 className="text-base font-semibold text-slate-900">No documents yet</h3>
              <p className="mx-auto mt-1 max-w-sm text-sm text-slate-500">
                Describe your event in one line and ClubDocs drafts the right documents for you.
              </p>
              {onNavigateToEvents && (
                <button type="button" onClick={onNavigateToEvents} className="btn-primary mt-5">
                  <Plus className="h-4 w-4" /> Create your first document
                </button>
              )}
            </>
          )}
        </div>
      ) : (
        <div className="surface-card overflow-hidden">
          {selectedIds.size > 0 && (
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 bg-slate-50 px-4 py-2 text-sm">
              <span className="font-medium text-slate-800">{selectedIds.size} selected</span>
              <div className="flex items-center gap-2">
                <button type="button" className="btn-ghost btn-sm" onClick={() => setSelectedIds(new Set())}>
                  Clear
                </button>
                <button
                  type="button"
                  onClick={() => setToDelete(documents.filter((d) => selectedIds.has(d.id)))}
                  className="btn-danger btn-sm"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  Delete selected
                </button>
              </div>
            </div>
          )}

          {/* Desktop and tablet: table */}
          <div className="hidden md:block">
            <table className="data-table table-fixed">
              <thead>
                <tr>
                  <th className="w-10 !pr-0">
                    <input
                      type="checkbox"
                      aria-label="Select all deletable documents on this page"
                      className="h-4 w-4 rounded border-slate-300 text-brand-700 focus:ring-brand-500"
                      checked={allOnPageSelected}
                      onChange={(e) => setSelectedIds(e.target.checked ? new Set(deletableOnPage.map((d) => d.id)) : new Set())}
                    />
                  </th>
                  <th>Document</th>
                  <th className="hidden w-44 xl:table-cell">Event</th>
                  <th className="w-32">Created</th>
                  <th className="w-44">Status</th>
                  <th className="w-32"><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody>
                {documents.map((doc) => (
                  <tr key={doc.id} className={`transition-colors ${selectedIds.has(doc.id) ? 'bg-brand-50/40' : 'hover:bg-slate-50/70'}`}>
                    <td className="!pr-0">
                      {isDeletable(doc.status) && (
                        <input
                          type="checkbox"
                          aria-label={`Select ${doc.title}`}
                          className="h-4 w-4 rounded border-slate-300 text-brand-700 focus:ring-brand-500"
                          checked={selectedIds.has(doc.id)}
                          onChange={(e) => toggleOne(doc.id, e.target.checked)}
                        />
                      )}
                    </td>
                    <td>
                      <div className="flex min-w-0 items-center gap-3">
                        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-500">
                          <FileText className="h-4 w-4" />
                        </span>
                        <div className="min-w-0">
                          <Link
                            to={docLink(doc.id)}
                            className="block truncate font-medium text-slate-900 hover:text-brand-700"
                            title={doc.title}
                          >
                            {doc.title}
                          </Link>
                          <p className="mt-0.5 flex min-w-0 items-center gap-1.5 truncate text-xs text-slate-500">
                            {doc.ref_no ? <span className="font-mono">{doc.ref_no}</span> : <span className="italic">No reference</span>}
                            <span aria-hidden="true">·</span>
                            <span className="truncate">{doc.template_name || doc.template_slug}</span>
                          </p>
                        </div>
                      </div>
                    </td>
                    <td className="hidden truncate text-slate-600 xl:table-cell" title={doc.event_title || ''}>
                      {doc.event_title || <span className="text-slate-400">—</span>}
                    </td>
                    <td className="whitespace-nowrap text-slate-600">{fmtDate(doc.created_at)}</td>
                    <td>
                      <StatusBadge status={doc.status} />
                    </td>
                    <td>
                      <div className="flex items-center justify-end gap-1">
                        <Link to={docLink(doc.id)} className="btn-secondary btn-sm">
                          {reviewMode ? 'Open to submit' : 'Open'}
                        </Link>
                        {rowMenu(doc)}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Phones: cards */}
          <ul className="divide-y divide-slate-100 md:hidden">
            {documents.map((doc) => (
              <li key={doc.id} className="flex items-start gap-3 px-4 py-3.5">
                {isDeletable(doc.status) && (
                  <input
                    type="checkbox"
                    aria-label={`Select ${doc.title}`}
                    className="mt-1 h-5 w-5 shrink-0 rounded border-slate-300 text-brand-700"
                    checked={selectedIds.has(doc.id)}
                    onChange={(e) => toggleOne(doc.id, e.target.checked)}
                  />
                )}
                <Link to={docLink(doc.id)} className="min-w-0 flex-1">
                  <p className="font-medium leading-snug text-slate-900">{doc.title}</p>
                  <p className="mt-1 truncate text-xs text-slate-500">
                    {doc.ref_no ? <span className="font-mono">{doc.ref_no}</span> : 'No reference'} · {fmtDate(doc.created_at)}
                  </p>
                  <div className="mt-2">
                    <StatusBadge status={doc.status} />
                  </div>
                </Link>
                {rowMenu(doc)}
              </li>
            ))}
          </ul>

          {/* Pagination Footer */}
          <div className="flex flex-col items-center justify-between gap-3 border-t border-slate-200 px-4 py-3 text-sm text-slate-600 sm:flex-row">
            <div className="flex items-center gap-2">
              <span className="hidden sm:inline">Rows</span>
              <select
                value={pageSize}
                onChange={(e) => {
                  setPageSize(Number(e.target.value));
                  setPage(1);
                }}
                className="input-field h-9 w-auto pr-8"
                aria-label="Rows per page"
              >
                <option value={10}>10</option>
                <option value={25}>25</option>
                <option value={50}>50</option>
              </select>
              <span>
                {Math.min((page - 1) * pageSize + 1, total)}–{Math.min(page * pageSize, total)} of {total}
              </span>
            </div>
            <div className="flex items-center gap-1">
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => setPage(page - 1)}
                className="btn-icon disabled:opacity-40"
                aria-label="Previous page"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <span className="px-2 font-medium text-slate-700">
                Page {page} of {totalPages}
              </span>
              <button
                type="button"
                disabled={page >= totalPages}
                onClick={() => setPage(page + 1)}
                className="btn-icon disabled:opacity-40"
                aria-label="Next page"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      )}

      {toDelete && (
        <DeleteDocsDialog
          clubId={clubId}
          docs={toDelete}
          onClose={() => setToDelete(null)}
          onDone={() => {
            setToDelete(null);
            fetchDocuments();
          }}
        />
      )}
      {trashOpen && <TrashDialog clubId={clubId} onClose={() => setTrashOpen(false)} onRestored={fetchDocuments} />}

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

              <div className="flex flex-wrap items-center gap-2">
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
