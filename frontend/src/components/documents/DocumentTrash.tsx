import React, { useEffect, useState } from 'react';
import { Trash2, RotateCcw, X, Ban } from 'lucide-react';
import { api } from '../../api/client';
import { TrashItem } from '../../types';
import { notify } from '../common/Toaster';

const fmtDate = (iso?: string | null) => (iso ? new Date(iso).toLocaleDateString('en-GB') : '');

/** Statuses that can be moved to the Trash (approved documents are cancelled instead). */
export const isDeletable = (status?: string) => status !== 'approved' && status !== 'cancelled';

interface DeleteDocsDialogProps {
  clubId: string | number;
  docs: { id: string; title: string; ref_no?: string | null }[];
  onClose: () => void;
  onDone: () => void;
}

/** Asks before moving one or more documents to the Trash, then reports what was skipped. */
export const DeleteDocsDialog: React.FC<DeleteDocsDialogProps> = ({ clubId, docs, onClose, onDone }) => {
  const [busy, setBusy] = useState(false);
  const one = docs.length === 1;

  const confirm = async () => {
    setBusy(true);
    try {
      if (one) {
        await api.documents.remove(clubId, docs[0].id);
        notify(`"${docs[0].title}" moved to Trash. You can restore it for 30 days.`, 'success');
      } else {
        const res = await api.documents.bulkRemove(clubId, docs.map((d) => d.id));
        if (res.deleted.length) notify(`${res.deleted.length} document(s) moved to Trash.`, 'success');
        if (res.skipped.length) {
          notify(`${res.skipped.length} not deleted: ${res.skipped.map((s) => s.reason).filter((v, i, a) => a.indexOf(v) === i).join(' ')}`, 'error');
        }
      }
      onDone();
    } catch (err: any) {
      notify(err.message || 'Could not delete the document.', 'error');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="delete-docs-title"
        className="w-full max-w-md rounded-xl bg-white p-5 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-red-50">
            <Trash2 className="h-5 w-5 text-red-600" />
          </span>
          <div className="min-w-0 flex-1">
            <h2 id="delete-docs-title" className="text-base font-bold text-slate-900">
              {one ? 'Delete this document?' : `Delete ${docs.length} documents?`}
            </h2>
            <p className="mt-1 text-sm text-slate-600">
              {one ? 'It' : 'They'} will move to the Trash and can be restored for 30 days. Reference numbers are never reused.
            </p>
            <ul className="mt-3 max-h-40 space-y-1 overflow-y-auto text-sm">
              {docs.map((d) => (
                <li key={d.id} className="truncate text-slate-800">
                  • {d.title}
                  {d.ref_no && <span className="ml-1 font-mono text-xs text-slate-500">({d.ref_no})</span>}
                </li>
              ))}
            </ul>
          </div>
        </div>
        <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <button type="button" className="btn-secondary justify-center" onClick={onClose} disabled={busy}>
            Keep {one ? 'it' : 'them'}
          </button>
          <button
            type="button"
            onClick={confirm}
            disabled={busy}
            className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-50"
          >
            <Trash2 className="h-4 w-4" />
            {busy ? 'Deleting…' : 'Move to Trash'}
          </button>
        </div>
      </div>
    </div>
  );
};

interface CancelDocDialogProps {
  clubId: string | number;
  doc: { id: string; title: string; ref_no?: string | null };
  onClose: () => void;
  onDone: () => void;
}

/** Withdraws an approved document; its verification code then reports the cancellation. */
export const CancelDocDialog: React.FC<CancelDocDialogProps> = ({ clubId, doc, onClose, onDone }) => {
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);

  const confirm = async () => {
    setBusy(true);
    try {
      await api.documents.cancel(clubId, doc.id, reason.trim());
      notify(`"${doc.title}" was cancelled. Its verification code now shows it as cancelled.`, 'success');
      onDone();
    } catch (err: any) {
      notify(err.message || 'Could not cancel the document.', 'error');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="cancel-doc-title"
        className="w-full max-w-md rounded-xl bg-white p-5 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-amber-50">
            <Ban className="h-5 w-5 text-amber-600" />
          </span>
          <div className="min-w-0 flex-1">
            <h2 id="cancel-doc-title" className="text-base font-bold text-slate-900">Cancel this approved document?</h2>
            <p className="mt-1 text-sm text-slate-600">
              Approved documents can't be deleted because printed copies may exist. Cancelling removes it from the list,
              and anyone who checks its verification code will see it was cancelled. This can't be undone.
            </p>
            <p className="mt-2 truncate text-sm font-semibold text-slate-800">
              {doc.title}
              {doc.ref_no && <span className="ml-1 font-mono text-xs font-normal text-slate-500">({doc.ref_no})</span>}
            </p>
            <label htmlFor="cancel-reason" className="field-label mt-3">Reason (shown on the verify page)</label>
            <input
              id="cancel-reason"
              className="input-field w-full"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="e.g. Event postponed"
              maxLength={500}
            />
          </div>
        </div>
        <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <button type="button" className="btn-secondary justify-center" onClick={onClose} disabled={busy}>
            Keep it
          </button>
          <button
            type="button"
            onClick={confirm}
            disabled={busy || reason.trim().length < 3}
            className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-amber-600 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-700 disabled:opacity-50"
          >
            <Ban className="h-4 w-4" />
            {busy ? 'Cancelling…' : 'Cancel document'}
          </button>
        </div>
      </div>
    </div>
  );
};

interface TrashDialogProps {
  clubId: string | number;
  onClose: () => void;
  /** Called after a restore so the document list can refresh */
  onRestored: () => void;
}

/** Deleted documents (restorable for 30 days) and cancelled approved documents. */
export const TrashDialog: React.FC<TrashDialogProps> = ({ clubId, onClose, onRestored }) => {
  const [items, setItems] = useState<TrashItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = () => {
    setError(null);
    api.documents
      .trash(clubId)
      .then(setItems)
      .catch((err) => setError(err.message || 'Could not load the Trash.'));
  };
  useEffect(load, [clubId]);

  const restore = async (item: TrashItem) => {
    setBusyId(item.id);
    try {
      await api.documents.restore(clubId, item.id);
      notify(`"${item.title}" restored.`, 'success');
      setItems((prev) => (prev || []).filter((i) => i.id !== item.id));
      onRestored();
    } catch (err: any) {
      notify(err.message || 'Could not restore the document.', 'error');
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-900/50 p-0 sm:items-center sm:p-4" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="trash-title"
        className="flex max-h-[85vh] w-full max-w-2xl flex-col overflow-hidden rounded-t-2xl bg-white shadow-2xl sm:rounded-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
          <div>
            <h2 id="trash-title" className="flex items-center gap-2 text-base font-bold text-slate-900">
              <Trash2 className="h-4 w-4 text-slate-500" /> Trash
            </h2>
            <p className="text-xs text-slate-500">Deleted documents stay here for 30 days, then they are removed for good.</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="flex h-10 w-10 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100"
            aria-label="Close Trash"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-3 sm:p-4">
          {error && <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}
          {!error && items === null && <p className="p-6 text-center text-sm text-slate-500">Loading…</p>}
          {items && items.length === 0 && <p className="p-8 text-center text-sm text-slate-500">The Trash is empty.</p>}
          <ul className="space-y-2">
            {(items || []).map((item) => (
              <li key={item.id} className="flex flex-col gap-2 rounded-lg border border-slate-200 p-3 sm:flex-row sm:items-center">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-slate-900">{item.title}</p>
                  <p className="mt-0.5 text-xs text-slate-500">
                    {item.ref_no && <span className="mr-1 font-mono">{item.ref_no} ·</span>}
                    {item.cancelled ? 'Cancelled' : 'Deleted'} {fmtDate(item.deleted_at)}
                    {item.deleted_by ? ` by ${item.deleted_by}` : ''}
                  </p>
                  {item.cancelled ? (
                    <p className="mt-1 text-xs text-amber-700">
                      Kept so its verification code shows it was cancelled{item.cancel_reason ? `: ${item.cancel_reason}` : '.'}
                    </p>
                  ) : (
                    item.purge_on && <p className="mt-1 text-xs text-slate-500">Removed for good on {fmtDate(item.purge_on)}</p>
                  )}
                </div>
                {item.can_restore && (
                  <button
                    type="button"
                    onClick={() => restore(item)}
                    disabled={busyId === item.id}
                    className="btn-secondary justify-center min-h-[40px]"
                  >
                    <RotateCcw className="h-4 w-4" />
                    {busyId === item.id ? 'Restoring…' : 'Restore'}
                  </button>
                )}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
};
