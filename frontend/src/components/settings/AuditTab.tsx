import React, { useState, useEffect } from 'react';
import { AuditLog } from '../../types';
import { api } from '../../api/client';
import { ShieldAlert, RefreshCw } from 'lucide-react';

interface AuditTabProps {
  clubId: string | number;
}

/** Readable label for an audit action code, e.g. "document_approved" -> "Document approved". */
const actionLabel = (code: string) => {
  const s = code.replace(/_/g, ' ');
  return s.charAt(0).toUpperCase() + s.slice(1);
};

/** Short "key: value" summary of an entry's details, skipping internal ids. */
const metaSummary = (meta: Record<string, any> | null | undefined) =>
  Object.entries(meta || {})
    .filter(([k, v]) => v !== null && v !== '' && !/(^|_)id$|hash/.test(k))
    .slice(0, 4)
    .map(([k, v]) => `${k.replace(/_/g, ' ')}: ${typeof v === 'object' ? JSON.stringify(v) : String(v)}`)
    .join(' · ');

export const AuditTab: React.FC<AuditTabProps> = ({ clubId }) => {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchLogs = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.clubs.getAuditLogs(clubId);
      setLogs(data);
    } catch (err: any) {
      setError(err.message || 'Could not load the activity log.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, [clubId]);

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <ShieldAlert className="w-6 h-6 text-slate-700" />
            <h2 className="text-xl font-bold text-slate-900">Security & Operational Audit Log</h2>
          </div>
          <p className="mt-1 text-xs text-slate-500">
            Immutable system audit logs recording authentication attempts, role changes, and document generation events.
          </p>
        </div>

        <button
          type="button"
          onClick={fetchLogs}
          disabled={loading}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
          <span className="text-xs font-semibold text-slate-600">
            Audit Records ({logs.length})
          </span>
          <span className="text-xs text-slate-400">Latest 200 entries</span>
        </div>

        {error ? (
          <div className="p-8 text-center text-red-600 text-sm">{error}</div>
        ) : loading ? (
          <div className="p-8 text-center text-slate-400 text-sm">Loading audit logs...</div>
        ) : logs.length === 0 ? (
          <div className="p-8 text-center text-slate-500 text-sm">No audit activity logged yet.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs min-w-[680px]">
              <thead className="bg-slate-100/60 text-slate-600 uppercase text-xs tracking-wider border-b border-slate-200">
                <tr>
                  <th className="py-3 px-6">Timestamp</th>
                  <th className="py-3 px-6">Actor</th>
                  <th className="py-3 px-6">Action</th>
                  <th className="py-3 px-6">Resource</th>
                  <th className="py-3 px-6">IP Address</th>
                  <th className="py-3 px-6">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {logs.map((log) => (
                  <tr key={log.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="py-3.5 px-6 font-mono text-slate-500 text-xs whitespace-nowrap">
                      {new Date(log.created_at).toLocaleString('en-IN', {
                        day: '2-digit',
                        month: 'short',
                        year: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                        second: '2-digit',
                      })}
                    </td>
                    <td className="py-3.5 px-6">
                      <span className="block font-medium text-slate-900">{log.actor_name || 'System'}</span>
                      {log.actor_email && <span className="block text-slate-500">{log.actor_email}</span>}
                    </td>
                    <td className="py-3.5 px-6">
                      <span className="bg-slate-100 text-slate-800 text-xs px-2 py-0.5 rounded font-medium border border-slate-200 whitespace-nowrap">
                        {actionLabel(log.action)}
                      </span>
                    </td>
                    <td className="py-3.5 px-6 text-slate-600 text-xs capitalize">
                      {log.entity_type.replace(/_/g, ' ')}
                    </td>
                    <td className="py-3.5 px-6 font-mono text-slate-500 text-xs">
                      {log.ip || '—'}
                    </td>
                    <td className="py-3.5 px-6 text-slate-600 text-xs max-w-xs truncate" title={metaSummary(log.meta)}>
                      {metaSummary(log.meta) || '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
