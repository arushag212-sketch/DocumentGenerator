import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import {
  ArrowLeft,
  Download,
  Mail,
  Send,
  CheckCircle2,
  RotateCcw,
  ShieldCheck,
  Pencil,
  MessageSquare,
  AlertCircle,
  X,
  Copy,
  Check,
  ExternalLink,
  Trash2,
  Ban,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import { DocumentActivity, EditableField, GeneratedDocument } from '../types';
import { CancelDocDialog, DeleteDocsDialog, isDeletable } from '../components/documents/DocumentTrash';

const STATUS: Record<string, { label: string; className: string }> = {
  ready: { label: 'Ready', className: 'bg-slate-100 text-slate-700 border-slate-200' },
  generated: { label: 'Ready', className: 'bg-slate-100 text-slate-700 border-slate-200' },
  submitted: { label: 'Awaiting review', className: 'bg-amber-50 text-amber-800 border-amber-200' },
  changes_requested: { label: 'Changes requested', className: 'bg-red-50 text-red-700 border-red-200' },
  approved: { label: 'Approved', className: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
  cancelled: { label: 'Cancelled', className: 'bg-amber-50 text-amber-800 border-amber-200' },
};

const ACTION_TEXT: Record<DocumentActivity['action'], string> = {
  submitted: 'submitted for review',
  approved: 'approved',
  changes_requested: 'requested changes',
  comment: 'commented',
  revised: 'edited the document',
  emailed: 'emailed the document',
};

export function StatusBadge({ status }: { status: string }) {
  const s = STATUS[status] || { label: status, className: 'bg-slate-100 text-slate-700 border-slate-200' };
  return <span className={`badge ${s.className}`}>{s.label}</span>;
}

function formatDate(value: string) {
  const d = new Date(value);
  return isNaN(d.getTime()) ? value : d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}

function EmailDialog({
  onClose,
  onSend,
}: {
  onClose: () => void;
  onSend: (to: string[], message: string, attach: 'pdf' | 'docx' | 'both') => Promise<void>;
}) {
  const [to, setTo] = useState('');
  const [message, setMessage] = useState('');
  const [attach, setAttach] = useState<'pdf' | 'docx' | 'both'>('pdf');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const list = to.split(/[,;\s]+/).map((s) => s.trim()).filter(Boolean);
    if (list.length === 0) {
      setError('Enter at least one email address.');
      return;
    }
    setSending(true);
    setError(null);
    try {
      await onSend(list, message, attach);
    } catch (err: any) {
      setError(err?.detail?.message || err?.message || 'Could not send the email.');
      setSending(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-labelledby="email-title">
      <div className="absolute inset-0 bg-slate-900/30" onClick={onClose} />
      <form onSubmit={submit} className="relative w-full max-w-md surface-card p-4 sm:p-5 space-y-4 max-h-[85vh] sm:max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between">
          <h2 id="email-title" className="section-title">Email this document</h2>
          <button type="button" className="btn-ghost !p-2 min-w-[44px] min-h-[44px] flex items-center justify-center" onClick={onClose} aria-label="Close">
            <X className="w-4 h-4" />
          </button>
        </div>
        <div>
          <label className="field-label" htmlFor="email-to">To</label>
          <input id="email-to" className="input-field" placeholder="hod.cse@svnit.ac.in, office@svnit.ac.in" value={to} onChange={(e) => setTo(e.target.value)} autoFocus />
          <p className="text-xs text-slate-500 mt-1">Separate several addresses with commas.</p>
        </div>
        <div>
          <label className="field-label" htmlFor="email-msg">Message (optional)</label>
          <textarea id="email-msg" className="input-field" rows={4} value={message} onChange={(e) => setMessage(e.target.value)} />
        </div>
        <fieldset>
          <legend className="field-label">Attach</legend>
          <div className="flex gap-4 text-sm text-slate-700">
            {(['pdf', 'docx', 'both'] as const).map((a) => (
              <label key={a} className="inline-flex items-center gap-1.5">
                <input type="radio" name="attach" checked={attach === a} onChange={() => setAttach(a)} />
                {a === 'both' ? 'PDF and Word' : a === 'pdf' ? 'PDF' : 'Word'}
              </label>
            ))}
          </div>
        </fieldset>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <div className="flex justify-end gap-2">
          <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn-primary" disabled={sending}>
            <Send className="w-4 h-4" />
            {sending ? 'Sending…' : 'Send'}
          </button>
        </div>
      </form>
    </div>
  );
}

function FieldInput({ field, value, onChange }: { field: EditableField; value: any; onChange: (v: any) => void }) {
  const id = `field-${field.key}`;
  const common = { id, className: 'input-field', value: value ?? '', onChange: (e: any) => onChange(e.target.value) };
  if (field.type === 'textarea' || field.type === 'long_text' || (typeof value === 'string' && value.length > 80)) {
    return <textarea {...common} rows={3} />;
  }
  if (field.type === 'number' || field.type === 'integer') return <input {...common} type="number" />;
  return <input {...common} type="text" />;
}

export const DocumentDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const { activeClub } = useAuth();
  const clubId = activeClub?.id;
  // ?review=1 (from the dashboard's "Send a document for review" step) points at the review box
  const [searchParams] = useSearchParams();
  const guideToReview = searchParams.get('review') === '1';
  const reviewRef = useRef<HTMLDivElement>(null);
  const [highlightReview, setHighlightReview] = useState(false);

  const [doc, setDoc] = useState<GeneratedDocument | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const [editing, setEditing] = useState(false);
  const [values, setValues] = useState<Record<string, any>>({});
  const [note, setNote] = useState('');
  const [comment, setComment] = useState('');
  const [emailOpen, setEmailOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [cancelOpen, setCancelOpen] = useState(false);
  const navigate = useNavigate();
  const [copied, setCopied] = useState(false);

  const load = useCallback(async () => {
    if (!clubId || !id) return;
    try {
      const d = await api.documents.get(clubId, id);
      setDoc(d);
      setValues(Object.fromEntries((d.editable_fields || []).map((f) => [f.key, f.value])));
      setError(null);
    } catch (e: any) {
      setError(e?.message || 'Could not load the document.');
    } finally {
      setLoading(false);
    }
  }, [clubId, id]);

  useEffect(() => {
    setLoading(true);
    load();
  }, [load]);

  const changes = useMemo(() => {
    const out: Record<string, any> = {};
    for (const f of doc?.editable_fields || []) {
      if (String(values[f.key] ?? '') !== String(f.value ?? '')) out[f.key] = values[f.key];
    }
    return out;
  }, [values, doc]);

  const run = async (key: string, fn: () => Promise<any>, success: string) => {
    setBusy(key);
    setNotice(null);
    setError(null);
    try {
      await fn();
      setNotice(success);
      await load();
    } catch (e: any) {
      setError(e?.detail?.message || (typeof e?.detail === 'string' ? e.detail : null) || e?.message || 'Something went wrong.');
    } finally {
      setBusy(null);
    }
  };

  useEffect(() => {
    if (!guideToReview || !doc || !reviewRef.current) return;
    reviewRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
    setHighlightReview(true);
    const t = window.setTimeout(() => setHighlightReview(false), 2500);
    return () => window.clearTimeout(t);
  }, [guideToReview, doc?.id]);

  if (loading) {
    return (
      <div className="flex justify-center py-24">
        <div className="h-6 w-6 border-2 border-brand-700 border-t-transparent rounded-full animate-spin" role="status" aria-label="Loading" />
      </div>
    );
  }

  if (!doc || !clubId) {
    return (
      <div className="max-w-md mx-auto py-20 px-4 text-center">
        <AlertCircle className="w-8 h-8 text-slate-300 mx-auto mb-3" />
        <h1 className="section-title">Document not found</h1>
        <p className="text-sm text-slate-500 mt-1">{error || 'It may have been deleted, or it belongs to another club.'}</p>
        <Link to="/documents" className="btn-secondary mt-5 inline-flex">Back to documents</Link>
      </div>
    );
  }

  const approvedEntry = (doc.activity || []).find((a) => a.action === 'approved' && a.verification_code);
  const vCode = (doc as any)?.verification_code || (doc.versions?.[0] as any)?.verification_code || approvedEntry?.verification_code;
  const canSubmit = doc.can_edit && ['ready', 'generated', 'changes_requested'].includes(doc.status);
  const canDecide = doc.can_review && doc.status === 'submitted';
  const fields = doc.editable_fields || [];
  const versions = [...(doc.versions || [])].sort((a, b) => b.version_no - a.version_no);
  const base = `/api/v1/clubs/${clubId}/documents/${doc.id}`;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-8 py-8">
      <Link to="/documents" className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-900 mb-4">
        <ArrowLeft className="w-4 h-4" /> Documents
      </Link>

      <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4 mb-6">
        <div className="min-w-0">
          <p className="text-sm text-slate-500">{doc.template_name || 'Document'}</p>
          <h1 className="page-title truncate">{doc.title}</h1>
          <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-slate-500">
            <span className="font-mono text-slate-700">{doc.ref_no || 'No reference number'}</span>
            <span>Version {doc.current_version_no}</span>
            <StatusBadge status={doc.status} />
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <a href={`${base}/download?format=pdf`} className="btn-primary">
            <Download className="w-4 h-4" /> PDF
          </a>
          <a href={`${base}/download?format=docx`} className="btn-secondary">
            <Download className="w-4 h-4" /> Word
          </a>
          {doc.can_edit && (
            <button type="button" className="btn-secondary" onClick={() => setEmailOpen(true)}>
              <Mail className="w-4 h-4" /> Email
            </button>
          )}
          {doc.can_edit && isDeletable(doc.status) && (
            <button
              type="button"
              className="btn-secondary text-red-700 hover:bg-red-50"
              onClick={() => setDeleteOpen(true)}
              title="Move to Trash (restorable for 30 days)"
            >
              <Trash2 className="w-4 h-4" /> Delete
            </button>
          )}
          {doc.can_review && doc.status === 'approved' && (
            <button
              type="button"
              className="btn-secondary text-amber-700 hover:bg-amber-50"
              onClick={() => setCancelOpen(true)}
              title="Withdraw this approved document"
            >
              <Ban className="w-4 h-4" /> Cancel document
            </button>
          )}
        </div>
      </div>

      {notice && <div className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-2.5 text-sm text-emerald-800">{notice}</div>}
      {error && <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-2.5 text-sm text-red-700">{error}</div>}

      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_360px] gap-6 items-start">
        {/* Preview */}
        <section aria-label="Preview" className="space-y-4">
          {doc.page_images.map((src, i) => (
            <img
              key={src}
              src={src}
              alt={`Page ${i + 1} of ${doc.page_images.length}`}
              className="w-full bg-white border border-slate-200 rounded-lg shadow-sm"
              loading={i === 0 ? 'eager' : 'lazy'}
            />
          ))}
        </section>

        <aside className="space-y-4 lg:sticky lg:top-6">
          {/* Verification Code */}
          {vCode && (
            <div className="surface-card p-5">
              <div className="flex items-center justify-between mb-2">
                <h2 className="text-sm font-semibold text-slate-900 flex items-center gap-1.5">
                  <ShieldCheck className="w-4 h-4 text-emerald-600" />
                  Verification code
                </h2>
                <Link
                  to={`/verify/${vCode}`}
                  target="_blank"
                  rel="noreferrer"
                  className="text-xs font-medium text-brand-700 hover:underline inline-flex items-center gap-1"
                >
                  Open verify page <ExternalLink className="w-3 h-3" />
                </Link>
              </div>
              <p className="text-xs text-slate-500 mb-3">
                Printed in the footer of this document. Anyone can verify it without signing in.
              </p>
              <div className="flex items-center justify-between gap-2 p-2 bg-slate-50 border border-slate-200 rounded-lg">
                <code className="font-mono text-xs font-semibold text-slate-800 tracking-wider">
                  {vCode}
                </code>
                <button
                  type="button"
                  onClick={() => {
                    navigator.clipboard.writeText(vCode);
                    setCopied(true);
                    setTimeout(() => setCopied(false), 2000);
                  }}
                  className="btn-secondary text-xs py-1 px-2 flex items-center gap-1"
                  title="Copy verification code"
                >
                  {copied ? (
                    <>
                      <Check className="w-3.5 h-3.5 text-emerald-600" /> Copied
                    </>
                  ) : (
                    <>
                      <Copy className="w-3.5 h-3.5" /> Copy
                    </>
                  )}
                </button>
              </div>
            </div>
          )}

          {/* Review */}
          <div
            ref={reviewRef}
            className={`surface-card p-5 scroll-mt-24 transition-shadow duration-500 ${highlightReview ? 'ring-2 ring-brand-500 ring-offset-2 shadow-lg' : ''}`}
          >
            <h2 className="section-title mb-3">Review</h2>
            {guideToReview && canSubmit && (
              <p className="mb-3 rounded-lg bg-brand-50 px-3 py-2 text-xs text-brand-800">
                Check the document preview. When it looks right, add a note if you like and click <strong>Submit for review</strong>.
                A club admin then approves it.
              </p>
            )}
            {doc.status === 'approved' && approvedEntry ? (
              <div className="space-y-2 text-sm">
                <p className="flex items-center gap-2 text-emerald-700">
                  <ShieldCheck className="w-4 h-4" /> Approved by {approvedEntry.user_name}
                </p>
                <p className="text-slate-600">
                  Verification code{' '}
                  <Link to={`/verify/${approvedEntry.verification_code}`} className="font-mono text-brand-700 hover:underline">
                    {approvedEntry.verification_code}
                  </Link>
                </p>
                <p className="text-xs text-slate-500">The code is printed on the approved PDF. Anyone can check it without signing in.</p>
              </div>
            ) : doc.status === 'submitted' ? (
              <p className="text-sm text-slate-600">Waiting for a club admin to approve.</p>
            ) : doc.status === 'changes_requested' ? (
              <p className="text-sm text-slate-600">An admin asked for changes. Edit the document, then submit it again.</p>
            ) : (
              <p className="text-sm text-slate-600">Submit the document when it is ready for an admin to approve.</p>
            )}

            <div className="mt-4 space-y-2">
              {(canDecide || canSubmit) && (
                <textarea
                  className="input-field"
                  rows={2}
                  placeholder={canDecide ? 'Note to the author (required to request changes)' : 'Note for the reviewer (optional)'}
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  aria-label="Review note"
                />
              )}
              {canSubmit && (
                <button
                  type="button"
                  className="btn-primary w-full justify-center"
                  disabled={!!busy}
                  onClick={() =>
                    run('submit', () => api.documents.review(clubId, doc.id, 'submit', comment), 'Submitted for review.').then(() => setComment(''))
                  }
                >
                  <Send className="w-4 h-4" /> {busy === 'submit' ? 'Submitting…' : 'Submit for review'}
                </button>
              )}
              {canDecide && (
                <div className="flex gap-2">
                  <button
                    type="button"
                    className="btn-primary flex-1 justify-center"
                    disabled={!!busy}
                    onClick={() =>
                      run('approve', () => api.documents.review(clubId, doc.id, 'approve', comment), 'Approved. The PDF now carries a verification code.').then(() =>
                        setComment('')
                      )
                    }
                  >
                    <CheckCircle2 className="w-4 h-4" /> {busy === 'approve' ? 'Approving…' : 'Approve'}
                  </button>
                  <button
                    type="button"
                    className="btn-secondary flex-1 justify-center"
                    disabled={!!busy || !comment.trim()}
                    title={comment.trim() ? undefined : 'Add a note explaining what to change'}
                    onClick={() =>
                      run('changes', () => api.documents.review(clubId, doc.id, 'request-changes', comment), 'Changes requested.').then(() =>
                        setComment('')
                      )
                    }
                  >
                    <RotateCcw className="w-4 h-4" /> Request changes
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Edit */}
          {doc.can_edit && fields.length > 0 && (
            <div className="surface-card p-5">
              <div className="flex items-center justify-between mb-3">
                <h2 className="section-title">Details</h2>
                {!editing && (
                  <button type="button" className="btn-ghost text-sm" onClick={() => setEditing(true)}>
                    <Pencil className="w-4 h-4" /> Edit
                  </button>
                )}
              </div>
              {editing ? (
                <form
                  className="space-y-3"
                  onSubmit={(e) => {
                    e.preventDefault();
                    run(
                      'revise',
                      () => api.documents.revise(clubId, doc.id, changes, note || undefined),
                      'Saved as a new version. The reference number is unchanged.'
                    ).then(() => {
                      setEditing(false);
                      setNote('');
                    });
                  }}
                >
                  {fields.map((f) => (
                    <div key={f.key}>
                      <label className="field-label" htmlFor={`field-${f.key}`}>
                        {f.label}
                        {f.required && <span className="text-red-600"> *</span>}
                      </label>
                      <FieldInput field={f} value={values[f.key]} onChange={(v) => setValues((s) => ({ ...s, [f.key]: v }))} />
                    </div>
                  ))}
                  <div>
                    <label className="field-label" htmlFor="revise-note">What changed (optional)</label>
                    <input id="revise-note" className="input-field" value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. Corrected the venue" />
                  </div>
                  <div className="flex justify-end gap-2 pt-1">
                    <button
                      type="button"
                      className="btn-secondary"
                      onClick={() => {
                        setEditing(false);
                        setValues(Object.fromEntries(fields.map((f) => [f.key, f.value])));
                      }}
                    >
                      Cancel
                    </button>
                    <button type="submit" className="btn-primary" disabled={!!busy || Object.keys(changes).length === 0}>
                      {busy === 'revise' ? 'Saving…' : 'Save new version'}
                    </button>
                  </div>
                  {doc.status === 'approved' && (
                    <p className="text-xs text-amber-700">Editing an approved document creates a new version that needs approval again.</p>
                  )}
                </form>
              ) : (
                <dl className="space-y-2 text-sm">
                  {fields.map((f) => (
                    <div key={f.key} className="grid grid-cols-[7.5rem_1fr] gap-2">
                      <dt className="text-slate-500 truncate" title={f.label}>{f.label}</dt>
                      <dd className="text-slate-900 break-words whitespace-pre-line">{String(f.value || '—')}</dd>
                    </div>
                  ))}
                </dl>
              )}
            </div>
          )}

          {/* Versions */}
          <div className="surface-card p-5">
            <h2 className="section-title mb-3">Versions</h2>
            <ol className="space-y-3">
              {versions.map((v) => (
                <li key={v.id} className="text-sm">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium text-slate-900">Version {v.version_no}</span>
                    <span className="flex gap-3 text-xs">
                      <a className="text-brand-700 hover:underline" href={`${base}/download?format=pdf&v=${v.version_no}`}>PDF</a>
                      <a className="text-brand-700 hover:underline" href={`${base}/download?format=docx&v=${v.version_no}`}>Word</a>
                    </span>
                  </div>
                  <p className="text-xs text-slate-500">
                    {formatDate(v.created_at)}
                    {v.created_by ? ` · ${v.created_by}` : ''}
                  </p>
                  {v.change_summary && <p className="text-xs text-slate-600 mt-0.5">{v.change_summary}</p>}
                </li>
              ))}
            </ol>
          </div>

          {/* Activity */}
          <div className="surface-card p-5">
            <h2 className="section-title mb-3">Activity</h2>
            {(doc.activity || []).length === 0 ? (
              <p className="text-sm text-slate-500">No activity yet.</p>
            ) : (
              <ol className="space-y-3 mb-4">
                {(doc.activity || []).map((a) => (
                  <li key={a.id} className="text-sm">
                    <p className="text-slate-800">
                      <span className="font-medium">{a.user_name}</span> {ACTION_TEXT[a.action] || a.action}
                      <span className="text-slate-400"> · v{a.version_no}</span>
                    </p>
                    {a.comment && <p className="text-slate-600 whitespace-pre-line mt-0.5">{a.comment}</p>}
                    <p className="text-xs text-slate-400">{formatDate(a.created_at)}</p>
                  </li>
                ))}
              </ol>
            )}
            <form
              className="flex gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                if (!comment.trim()) return;
                run('comment', () => api.documents.review(clubId, doc.id, 'comments', comment), 'Comment added.').then(() => setComment(''));
              }}
            >
              <label htmlFor="comment" className="sr-only">Add a comment</label>
              <input id="comment" className="input-field" placeholder="Add a comment" value={comment} onChange={(e) => setComment(e.target.value)} />
              <button type="submit" className="btn-secondary flex-shrink-0" disabled={!comment.trim() || !!busy} aria-label="Post comment">
                <MessageSquare className="w-4 h-4" />
              </button>
            </form>
          </div>
        </aside>
      </div>

      {deleteOpen && (
        <DeleteDocsDialog
          clubId={clubId}
          docs={[{ id: doc.id, title: doc.title, ref_no: doc.ref_no }]}
          onClose={() => setDeleteOpen(false)}
          onDone={() => navigate('/documents')}
        />
      )}
      {cancelOpen && (
        <CancelDocDialog
          clubId={clubId}
          doc={{ id: doc.id, title: doc.title, ref_no: doc.ref_no }}
          onClose={() => setCancelOpen(false)}
          onDone={() => navigate('/documents')}
        />
      )}
      {emailOpen && (
        <EmailDialog
          onClose={() => setEmailOpen(false)}
          onSend={async (to, message, attach) => {
            const res = await api.documents.email(clubId, doc.id, { to, message: message || undefined, attach });
            setEmailOpen(false);
            setNotice(`Sent to ${res.sent_to.join(', ')}.`);
            load();
          }}
        />
      )}
    </div>
  );
};
