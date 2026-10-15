import React, { useState, useEffect } from 'react';
import {
  Calendar,
  FileText,
  Edit2,
  RefreshCw,
  Loader2,
  AlertCircle,
  CheckCircle,
} from 'lucide-react';
import { api } from '../api/client';
import { GeneratedDocument } from '../types';

interface EventsTabProps {
  clubId: string | number;
  onViewDocument: (doc: GeneratedDocument) => void;
  onNewDocumentForEvent?: (templateId: string, eventId: string) => void;
}

export const EventsTab: React.FC<EventsTabProps> = ({
  clubId,
  onViewDocument,
}) => {
  const [events, setEvents] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Edit Event State
  const [editingEvent, setEditingEvent] = useState<any | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [editEventCode, setEditEventCode] = useState('');
  const [editVenue, setEditVenue] = useState('');
  const [updateDocuments, setUpdateDocuments] = useState(true);
  const [saving, setSaving] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const fetchEvents = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.events.list(clubId);
      setEvents(res.items || []);
    } catch (err: any) {
      setError(err.message || 'Failed to load events');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEvents();
  }, [clubId]);

  const handleOpenEdit = (ev: any) => {
    setEditingEvent(ev);
    setEditTitle(ev.title);
    setEditEventCode(ev.event_code || '');
    setEditVenue(ev.record?.venue || '');
    setUpdateDocuments(true);
    setSuccessMsg(null);
  };

  const handleSaveEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingEvent) return;

    try {
      setSaving(true);
      setError(null);
      const mergedRecord = { ...(editingEvent.record || {}), venue: editVenue };
      const res = await api.events.update(
        clubId,
        editingEvent.id,
        {
          title: editTitle,
          event_code: editEventCode,
          record: mergedRecord,
        },
        updateDocuments
      );
      if (updateDocuments && res.documents && res.documents.length > 0) {
        const docList = res.documents
          .map((d: any) => `${d.title || d.template_slug} (v${d.current_version_no})`)
          .join(', ');
        setSuccessMsg(`Event updated. Re-rendered ${res.documents.length} document(s): ${docList}`);
      } else {
        setSuccessMsg('Event updated successfully.');
      }
      setEditingEvent(null);
      await fetchEvents();
    } catch (err: any) {
      setError(err.message || 'Failed to update event');
    } finally {
      setSaving(false);
    }
  };

  const handleViewDoc = async (docId: string) => {
    try {
      const doc = await api.documents.get(clubId, docId);
      onViewDocument(doc);
    } catch (err: any) {
      alert(`Could not load document: ${err.message}`);
    }
  };

  if (loading) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-12 text-center shadow-sm">
        <Loader2 className="w-8 h-8 text-[#1b365d] animate-spin mx-auto mb-3" />
        <p className="text-slate-600 text-sm font-medium">Loading event workflows and document packages...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 flex items-center gap-2">
            <Calendar className="w-5 h-5 text-[#1b365d]" />
            Events & Coordinated Document Packages
          </h2>
          <p className="text-xs text-slate-600 mt-1">
            Documents belonging to the same event share canonical details (Approval Note numbers, dates, venues, budgets).
          </p>
        </div>

        <button
          onClick={fetchEvents}
          className="inline-flex items-center gap-1.5 text-xs text-slate-600 bg-slate-100 hover:bg-slate-200 px-3 py-1.5 rounded-lg font-semibold transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh
        </button>
      </div>

      {successMsg && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-xs sm:text-sm text-emerald-800 flex items-center gap-2 font-medium">
          <CheckCircle className="w-4 h-4 flex-shrink-0 text-emerald-600" />
          <span>{successMsg}</span>
        </div>
      )}

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-xs sm:text-sm text-red-800 flex items-center gap-2 font-medium">
          <AlertCircle className="w-4 h-4 flex-shrink-0 text-red-600" />
          <span>{error}</span>
        </div>
      )}

      {events.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 p-12 text-center shadow-sm">
          <Calendar className="w-10 h-10 text-slate-300 mx-auto mb-2" />
          <h3 className="text-base font-bold text-slate-800">No Events Created Yet</h3>
          <p className="text-xs text-slate-500 mt-1 max-w-md mx-auto">
            When you generate a document with an event name (e.g. Permission Letter or Approval Note), an Event record is automatically created and links all subsequent documents for that event.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {events.map((ev) => (
            <div
              key={ev.id}
              className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 space-y-4 hover:border-slate-300 transition-all"
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-4">
                <div>
                  <div className="flex items-center gap-2.5">
                    <h3 className="text-lg font-bold text-slate-900">{ev.title}</h3>
                    {ev.event_code && (
                      <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200">
                        {ev.event_code}
                      </span>
                    )}
                    <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300">
                      {ev.status}
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 mt-1 flex items-center gap-2">
                    <span>Venue: <strong>{ev.record?.venue || '—'}</strong></span>
                    <span>•</span>
                    <span>Date: <strong>{ev.record?.document_date || ev.record?.dates || '—'}</strong></span>
                    <span>•</span>
                    <span>Participants: <strong>{ev.record?.expected_participants || '—'}</strong></span>
                  </p>
                </div>

                <button
                  type="button"
                  onClick={() => handleOpenEdit(ev)}
                  className="inline-flex items-center gap-1.5 text-xs font-semibold bg-slate-100 hover:bg-slate-200 text-slate-700 px-3 py-1.5 rounded-lg transition-colors"
                >
                  <Edit2 className="w-3.5 h-3.5 text-slate-500" />
                  Edit Event
                </button>
              </div>

              {/* Linked Documents List */}
              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs font-bold text-slate-700">
                  <span className="flex items-center gap-1.5">
                    <FileText className="w-4 h-4 text-amber-600" />
                    Generated Documents ({ev.documents?.length || 0})
                  </span>
                </div>

                {ev.documents && ev.documents.length > 0 ? (
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 pt-1">
                    {ev.documents.map((doc: any) => (
                      <div
                        key={doc.id}
                        onClick={() => handleViewDoc(doc.id)}
                        className="p-3 bg-slate-50/70 hover:bg-blue-50/40 rounded-lg border border-slate-200 hover:border-[#1b365d] transition-all cursor-pointer flex flex-col justify-between"
                      >
                        <div>
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-xs font-bold text-slate-900 capitalize truncate">
                              {doc.template_slug.replace(/_/g, ' ')}
                            </span>
                            <span className="text-[10px] font-mono text-slate-500">
                              v{doc.current_version_no}
                            </span>
                          </div>
                          <p className="text-[11px] font-mono font-medium text-amber-800">
                            {doc.ref_no || 'No ref number'}
                          </p>
                        </div>
                        <div className="mt-2 pt-2 border-t border-slate-200/60 flex items-center justify-between text-[10px] text-slate-500">
                          <span>{doc.status}</span>
                          <span className="text-[#1b365d] font-bold">Review →</span>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-slate-400 italic">
                    No documents generated under this event yet.
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Edit Event Modal */}
      {editingEvent && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl border border-slate-200 max-w-md w-full p-6 space-y-4">
            <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <Edit2 className="w-5 h-5 text-[#1b365d]" />
              Edit Event Context
            </h3>
            <p className="text-xs text-slate-500">
              Updating this event's canonical fields can automatically propagate and re-render all attached documents.
            </p>

            <form onSubmit={handleSaveEdit} className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  Event Title
                </label>
                <input
                  type="text"
                  value={editTitle}
                  onChange={(e) => setEditTitle(e.target.value)}
                  required
                  className="w-full text-xs p-2.5 rounded-lg border border-slate-300 focus:ring-2 focus:ring-[#1b365d]"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  Event Code
                </label>
                <input
                  type="text"
                  value={editEventCode}
                  onChange={(e) => setEditEventCode(e.target.value)}
                  placeholder="e.g. SIH, WORKSHOP"
                  className="w-full text-xs p-2.5 rounded-lg border border-slate-300 focus:ring-2 focus:ring-[#1b365d]"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  Event Venue
                </label>
                <input
                  type="text"
                  value={editVenue}
                  onChange={(e) => setEditVenue(e.target.value)}
                  placeholder="e.g. Seminar Hall, CC Lab 1"
                  className="w-full text-xs p-2.5 rounded-lg border border-slate-300 focus:ring-2 focus:ring-[#1b365d]"
                />
              </div>

              {/* UI Diff Preview */}
              {(() => {
                const oldVenue = editingEvent.record?.venue || '';
                const venueChanged = editVenue.trim() !== oldVenue.trim();
                const titleChanged = editTitle.trim() !== editingEvent.title.trim();
                const docCount = editingEvent.documents?.length || 0;

                if ((venueChanged || titleChanged) && docCount > 0) {
                  return (
                    <div className="p-3 bg-amber-50/80 rounded-lg border border-amber-300 text-xs space-y-1">
                      <div className="font-bold text-amber-900 flex items-center gap-1.5">
                        <AlertCircle className="w-3.5 h-3.5 text-amber-600" />
                        <span>Propagation Diff Preview</span>
                      </div>
                      {venueChanged && (
                        <p className="text-[11px] font-mono text-amber-950">
                          venue: <span className="line-through text-red-600">{oldVenue || '(none)'}</span> &rarr; <span className="text-emerald-700 font-bold">{editVenue}</span>, affects {docCount} documents
                        </p>
                      )}
                      {titleChanged && (
                        <p className="text-[11px] font-mono text-amber-950">
                          title: <span className="line-through text-red-600">{editingEvent.title}</span> &rarr; <span className="text-emerald-700 font-bold">{editTitle}</span>, affects {docCount} documents
                        </p>
                      )}
                    </div>
                  );
                }
                return null;
              })()}

              {editingEvent.documents && editingEvent.documents.length > 0 && (
                <div className="p-3 bg-blue-50/60 rounded-lg border border-blue-200 space-y-2">
                  <label className="flex items-center gap-2 cursor-pointer text-xs font-bold text-blue-900">
                    <input
                      type="checkbox"
                      checked={updateDocuments}
                      onChange={(e) => setUpdateDocuments(e.target.checked)}
                      className="rounded border-blue-400 text-[#1b365d] focus:ring-[#1b365d]"
                    />
                    <span>Update {editingEvent.documents.length} linked document(s)</span>
                  </label>
                  <p className="text-[11px] text-blue-800 leading-snug">
                    When checked, re-renders all linked documents via LibreOffice with the updated title, venue, and fields, creating new versions.
                  </p>
                </div>
              )}

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setEditingEvent(null)}
                  className="px-4 py-2 text-xs font-semibold text-slate-600 hover:text-slate-800"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="bg-[#1b365d] hover:bg-[#152a48] text-white px-5 py-2 rounded-lg text-xs font-bold transition-colors disabled:opacity-50"
                >
                  {saving
                    ? 'Updating...'
                    : updateDocuments && editingEvent.documents?.length > 0
                    ? `Update ${editingEvent.documents.length} documents`
                    : 'Save Changes'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
