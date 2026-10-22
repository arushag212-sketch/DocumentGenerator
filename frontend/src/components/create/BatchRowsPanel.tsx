import React, { useState } from 'react';
import { Table2, Upload, Link2, X } from 'lucide-react';
import { api } from '../../api/client';

export interface BatchRows {
  templateKey: string;
  templateName: string;
  rows: Record<string, string>[];
  mappedKeys: string[];
  source: string;
}

type Parsed = Awaited<ReturnType<typeof api.documents.parseRows>>;

/**
 * One document per row from a CSV file or a shared Google Sheet (e.g. a certificate for every
 * participant). The member maps the sheet's columns to the template's fields before using it.
 */
export const BatchRowsPanel: React.FC<{
  clubId: string | number;
  templates: { key: string; name: string }[];
  value: BatchRows | null;
  onChange: (v: BatchRows | null) => void;
}> = ({ clubId, templates, value, onChange }) => {
  const [open, setOpen] = useState(false);
  const [templateKey, setTemplateKey] = useState(
    () => templates.find((t) => /certificate|receipt|letter/i.test(t.name))?.key || templates[0]?.key || ''
  );
  const [sheetUrl, setSheetUrl] = useState('');
  const [parsed, setParsed] = useState<Parsed | null>(null);
  const [mapping, setMapping] = useState<Record<string, string | null>>({});
  const [source, setSource] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const read = async (src: { file?: File; sheetUrl?: string }, label: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.documents.parseRows(clubId, templateKey, src);
      setParsed(res);
      setMapping(res.mapping);
      setSource(label);
    } catch (e: any) {
      setError(typeof e?.detail === 'string' ? e.detail : e?.message || 'Could not read the rows.');
    } finally {
      setLoading(false);
    }
  };

  const apply = () => {
    if (!parsed) return;
    const rows = parsed.rows
      .map((row) => {
        const out: Record<string, string> = {};
        for (const [col, key] of Object.entries(mapping)) {
          if (key && row[col]?.trim()) out[key] = row[col].trim();
        }
        return out;
      })
      .filter((r) => Object.keys(r).length > 0);
    const t = templates.find((x) => x.key === templateKey);
    onChange({
      templateKey,
      templateName: t?.name || 'document',
      rows,
      mappedKeys: Array.from(new Set(Object.values(mapping).filter(Boolean) as string[])),
      source,
    });
    setOpen(false);
  };

  if (templates.length === 0) return null;

  if (value && !open) {
    return (
      <div className="surface-card p-4 flex items-center justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <Table2 className="w-5 h-5 text-brand-700 flex-shrink-0" />
          <p className="text-sm text-slate-700 truncate">
            <span className="font-medium text-slate-900">{value.rows.length}</span> {value.templateName} documents, one per row of{' '}
            <span className="font-medium">{value.source}</span>
          </p>
        </div>
        <div className="flex gap-2 flex-shrink-0">
          <button type="button" className="btn-ghost text-sm" onClick={() => setOpen(true)}>Change</button>
          <button type="button" className="btn-ghost !p-2.5 sm:!p-1.5 min-w-[44px] min-h-[44px] sm:min-w-0 sm:min-h-0 flex items-center justify-center" aria-label="Remove rows" onClick={() => onChange(null)}>
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>
    );
  }

  if (!open) {
    return (
      <button type="button" className="btn-secondary" onClick={() => setOpen(true)}>
        <Table2 className="w-4 h-4" />
        Make one per row from a spreadsheet
      </button>
    );
  }

  const fieldOptions = parsed?.fields || [];
  const missingRequired = fieldOptions.filter((f) => f.required && !Object.values(mapping).includes(f.key));

  return (
    <div className="surface-card p-5 space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="section-title">One document per row</h2>
          <p className="text-sm text-slate-600 mt-0.5">
            Upload a CSV or paste a Google Sheets link shared as &quot;Anyone with the link&quot;. Up to 300 rows.
          </p>
        </div>
        <button type="button" className="btn-ghost !p-2.5 sm:!p-1.5 min-w-[44px] min-h-[44px] sm:min-w-0 sm:min-h-0 flex items-center justify-center" aria-label="Close" onClick={() => setOpen(false)}>
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="grid sm:grid-cols-[1fr_auto] gap-3 items-end">
        <div>
          <label className="field-label" htmlFor="rows-template">Document</label>
          <select
            id="rows-template"
            className="input-field"
            value={templateKey}
            onChange={(e) => {
              setTemplateKey(e.target.value);
              setParsed(null);
            }}
          >
            {templates.map((t) => (
              <option key={t.key} value={t.key}>{t.name}</option>
            ))}
          </select>
        </div>
        <label className="btn-secondary cursor-pointer">
          <Upload className="w-4 h-4" />
          {loading ? 'Reading…' : 'Upload CSV'}
          <input
            type="file"
            accept=".csv,text/csv"
            className="sr-only"
            disabled={loading}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) read({ file: f }, f.name);
              e.target.value = '';
            }}
          />
        </label>
      </div>

      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (sheetUrl.trim()) read({ sheetUrl: sheetUrl.trim() }, 'the Google Sheet');
        }}
      >
        <label htmlFor="sheet-url" className="sr-only">Google Sheets link</label>
        <input
          id="sheet-url"
          className="input-field"
          placeholder="https://docs.google.com/spreadsheets/d/…"
          value={sheetUrl}
          onChange={(e) => setSheetUrl(e.target.value)}
        />
        <button type="submit" className="btn-secondary flex-shrink-0" disabled={loading || !sheetUrl.trim()}>
          <Link2 className="w-4 h-4" /> Read sheet
        </button>
      </form>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {parsed && (
        <div className="space-y-3">
          <p className="text-sm text-slate-700">
            {parsed.row_count} rows found. Match each column to a field, or leave it unused.
          </p>
          <div className="border border-slate-200 rounded-lg divide-y divide-slate-100 overflow-x-auto">
            {parsed.headers.map((h) => (
              <div key={h} className="grid grid-cols-1 sm:grid-cols-2 gap-2 sm:gap-3 items-center px-3 py-2">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-slate-900 truncate">{h}</p>
                  <p className="text-xs text-slate-500 truncate">e.g. {parsed.rows[0]?.[h] || '—'}</p>
                </div>
                <select
                  aria-label={`Field for column ${h}`}
                  className="input-field w-full rounded-lg !py-1.5"
                  value={mapping[h] || ''}
                  onChange={(e) => setMapping((m) => ({ ...m, [h]: e.target.value || null }))}
                >
                  <option value="">Not used</option>
                  {fieldOptions.map((f) => (
                    <option key={f.key} value={f.key}>
                      {f.label}
                      {f.required ? ' *' : ''}
                    </option>
                  ))}
                </select>
              </div>
            ))}
          </div>
          {missingRequired.length > 0 && (
            <p className="text-sm text-slate-600">
              Not in the sheet: {missingRequired.map((f) => f.label).join(', ')}. Fill these once below; they will be the same on every document.
            </p>
          )}
          <div className="flex justify-end">
            <button type="button" className="btn-primary" onClick={apply} disabled={!Object.values(mapping).some(Boolean)}>
              Use {parsed.row_count} rows
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
