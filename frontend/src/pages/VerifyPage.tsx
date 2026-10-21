import React, { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ShieldCheck, ShieldAlert, Upload, FileCheck2, FileX2 } from 'lucide-react';
import { api } from '../api/client';
import { VerificationResult } from '../types';

/** Public page: look up an approved document by its verification code and check a copy. */
export const VerifyPage: React.FC = () => {
  const { code = '' } = useParams();
  const navigate = useNavigate();
  const [input, setInput] = useState(code);
  const [result, setResult] = useState<VerificationResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [checking, setChecking] = useState(false);

  useEffect(() => {
    setResult(null);
    setError(null);
    if (!code) return;
    setLoading(true);
    api.verify
      .get(code)
      .then(setResult)
      .catch((e: any) => setError(e?.detail || e?.message || 'Verification failed.'))
      .finally(() => setLoading(false));
  }, [code]);

  const checkFile = async (file: File) => {
    setChecking(true);
    try {
      setResult(await api.verify.file(code, file));
    } catch (e: any) {
      setError(e?.detail || e?.message || 'Could not check the file.');
    } finally {
      setChecking(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <header className="h-14 flex items-center gap-2 px-4 sm:px-8 border-b border-slate-200 bg-white">
        <img src="/brand/svnit_crest.png" alt="" className="w-7 h-7 object-contain" />
        <span className="text-sm font-semibold text-slate-900">ClubDocs</span>
        <span className="text-xs text-slate-400">Document verification</span>
      </header>

      <main className="flex-1 w-full max-w-xl mx-auto px-4 py-10">
        <h1 className="page-title">Verify a document</h1>
        <p className="page-subtitle mb-6">
          Approved documents carry a verification code in their footer. Enter it to see who approved the document and when.
        </p>

        <form
          className="flex gap-2 mb-6"
          onSubmit={(e) => {
            e.preventDefault();
            if (input.trim()) navigate(`/verify/${encodeURIComponent(input.trim().toUpperCase())}`);
          }}
        >
          <label htmlFor="verify-code" className="sr-only">Verification code</label>
          <input
            id="verify-code"
            className="input-field font-mono uppercase"
            placeholder="XXXXXXXX-XXXXXXXX"
            value={input}
            onChange={(e) => setInput(e.target.value)}
          />
          <button type="submit" className="btn-primary flex-shrink-0">Verify</button>
        </form>

        {loading && <p className="text-sm text-slate-500">Checking…</p>}

        {error && !loading && (
          <div className="surface-card p-5 flex gap-3">
            <ShieldAlert className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-medium text-slate-900">Not verified</p>
              <p className="text-sm text-slate-600 mt-0.5">{error}</p>
            </div>
          </div>
        )}

        {result && !loading && (
          <div className="surface-card divide-y divide-slate-100">
            <div className="p-5 flex gap-3">
              <ShieldCheck className="w-5 h-5 text-emerald-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-medium text-slate-900">Approved document</p>
                <p className="text-sm text-slate-600 mt-0.5">This code belongs to a document approved in ClubDocs.</p>
              </div>
            </div>
            <dl className="p-5 grid grid-cols-[8rem_1fr] gap-y-2 text-sm">
              <dt className="text-slate-500">Document</dt>
              <dd className="text-slate-900">{result.document_title}</dd>
              <dt className="text-slate-500">Reference</dt>
              <dd className="text-slate-900 font-mono">{result.ref_no || '—'}</dd>
              <dt className="text-slate-500">Club</dt>
              <dd className="text-slate-900">{result.club_name}</dd>
              <dt className="text-slate-500">Version</dt>
              <dd className="text-slate-900">{result.version_no}</dd>
              <dt className="text-slate-500">Approved by</dt>
              <dd className="text-slate-900">{result.approved_by}</dd>
              <dt className="text-slate-500">Approved on</dt>
              <dd className="text-slate-900">{result.approved_at}</dd>
            </dl>
            <div className="p-5">
              <p className="text-sm font-medium text-slate-900 mb-1">Check a copy</p>
              <p className="text-sm text-slate-600 mb-3">
                Upload the PDF you received to confirm it is the approved file and has not been altered.
              </p>
              <label className="btn-secondary cursor-pointer">
                <Upload className="w-4 h-4" />
                {checking ? 'Checking…' : 'Choose PDF'}
                <input
                  type="file"
                  accept="application/pdf"
                  className="sr-only"
                  disabled={checking}
                  onChange={(e) => e.target.files?.[0] && checkFile(e.target.files[0])}
                />
              </label>
              {result.file_matches === true && (
                <p className="mt-3 flex items-center gap-2 text-sm text-emerald-700">
                  <FileCheck2 className="w-4 h-4" /> The file matches the approved document exactly.
                </p>
              )}
              {result.file_matches === false && (
                <p className="mt-3 flex items-center gap-2 text-sm text-red-700">
                  <FileX2 className="w-4 h-4" /> The file does not match. It may have been edited after approval.
                </p>
              )}
            </div>
          </div>
        )}

        <p className="mt-8 text-sm text-slate-500">
          Club member? <Link to="/login" className="text-brand-700 hover:underline">Sign in</Link>
        </p>
      </main>
    </div>
  );
};
