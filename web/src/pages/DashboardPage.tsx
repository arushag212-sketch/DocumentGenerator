import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { FilePlus2, LayoutTemplate, FileCheck2, Clock3, Files, Hourglass, ArrowRight } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import { ClubAnalytics } from '../types';
import { PageHeader } from '../components/AppShell';
import { GettingStarted } from '../components/onboarding/GettingStarted';

const STATUS_LABEL: Record<string, string> = {
  ready: 'Ready',
  submitted: 'Awaiting review',
  approved: 'Approved',
  changes_requested: 'Changes requested',
  draft: 'Draft',
  finalized: 'Finalized',
};

function StatTile({ label, value, hint, icon: Icon }: { label: string; value: React.ReactNode; hint?: string; icon: React.ElementType }) {
  return (
    <div className="surface-card p-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-500">{label}</p>
        <Icon className="w-4 h-4 text-slate-400" aria-hidden />
      </div>
      <p className="mt-2 text-2xl font-semibold text-slate-900 tabular-nums">{value}</p>
      {hint && <p className="mt-0.5 text-xs text-slate-500">{hint}</p>}
    </div>
  );
}

/** Documents per month: one series, one hue, bars anchored to the baseline, tooltip per bar. */
function MonthlyChart({ data }: { data: ClubAnalytics['by_month'] }) {
  const [hover, setHover] = useState<number | null>(null);
  const [asTable, setAsTable] = useState(false);
  const max = Math.max(1, ...data.map((d) => d.documents));
  return (
    <div className="surface-card p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="section-title">Documents generated per month</h2>
        <button type="button" className="text-xs text-slate-500 hover:text-slate-800 underline-offset-2 hover:underline" onClick={() => setAsTable(!asTable)}>
          {asTable ? 'Show chart' : 'Show as table'}
        </button>
      </div>
      {asTable ? (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-slate-500">
              <th className="font-medium py-1">Month</th>
              <th className="font-medium py-1 text-right">Documents</th>
            </tr>
          </thead>
          <tbody>
            {data.map((d) => (
              <tr key={d.month} className="border-t border-slate-100">
                <td className="py-1.5 text-slate-700">{d.month}</td>
                <td className="py-1.5 text-right tabular-nums text-slate-900">{d.documents}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div className="relative">
          <div className="flex items-end gap-3 h-40 border-b border-slate-200" role="img" aria-label="Documents generated per month">
            {data.map((d, i) => (
              <div
                key={d.month}
                className="relative flex-1 h-full flex items-end justify-center"
                onMouseEnter={() => setHover(i)}
                onMouseLeave={() => setHover(null)}
              >
                {hover === i && (
                  <div className="absolute bottom-full mb-1 px-2 py-1 rounded-md bg-slate-900 text-white text-xs whitespace-nowrap z-10">
                    {d.month}: <span className="font-semibold tabular-nums">{d.documents}</span>
                  </div>
                )}
                <div
                  className={`w-full max-w-[36px] rounded-t transition-colors ${hover === i ? 'bg-brand-800' : 'bg-brand-600'}`}
                  style={{ height: `${d.documents === 0 ? 0 : Math.max(3, (d.documents / max) * 100)}%` }}
                />
              </div>
            ))}
          </div>
          <div className="flex gap-3 mt-1.5">
            {data.map((d) => (
              <span key={d.month} className="flex-1 text-center text-xs text-slate-500">
                {d.month.split(' ')[0]}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function TemplateBreakdown({ data }: { data: ClubAnalytics['by_template'] }) {
  const max = Math.max(1, ...data.map((d) => d.count));
  return (
    <div className="surface-card p-5">
      <h2 className="section-title mb-4">Most used templates</h2>
      {data.length === 0 ? (
        <p className="text-sm text-slate-500">No documents yet.</p>
      ) : (
        <ul className="space-y-3">
          {data.map((t) => (
            <li key={t.name}>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-slate-700 truncate pr-3">{t.name}</span>
                <span className="tabular-nums text-slate-900">{t.count}</span>
              </div>
              <div className="h-1.5 bg-slate-100 rounded-full">
                <div className="h-1.5 bg-brand-600 rounded-full" style={{ width: `${(t.count / max) * 100}%` }} />
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export const DashboardPage: React.FC = () => {
  const { activeClub, user } = useAuth();
  const [stats, setStats] = useState<ClubAnalytics | null>(null);
  const [recent, setRecent] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!activeClub) return;
    setStats(null);
    api.analytics.get(activeClub.id).then(setStats).catch((e) => setError(e.message));
    api.documents
      .list(activeClub.id, { page_size: 6 } as any)
      .then((res: any) => setRecent(res.items || res || []))
      .catch(() => setRecent([]));
  }, [activeClub?.id]);

  const firstName = (user?.full_name || '').split(' ')[0];

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-8 py-8">
      <PageHeader
        title={firstName ? `Welcome, ${firstName}` : 'Dashboard'}
        description={activeClub?.name}
        actions={
          <>
            <Link to="/templates" className="btn-secondary">
              <LayoutTemplate className="w-4 h-4" />
              Templates
            </Link>
            <Link to="/home" className="btn-primary">
              <FilePlus2 className="w-4 h-4" />
              Create documents
            </Link>
          </>
        }
      />

      {error && <p className="text-sm text-red-600 mb-4">{error}</p>}

      <GettingStarted stats={stats} />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <StatTile label="This month" value={stats?.documents_this_month ?? '–'} hint="documents generated" icon={FilePlus2} />
        <StatTile label="All documents" value={stats?.documents_total ?? '–'} hint={stats ? `${stats.events_total} events` : undefined} icon={Files} />
        <StatTile label="Awaiting review" value={stats?.awaiting_review ?? '–'} hint={stats ? `${stats.approvals} approved` : undefined} icon={Hourglass} />
        <StatTile label="Time saved" value={stats ? `${stats.hours_saved} h` : '–'} hint="estimated, 25 min per document" icon={Clock3} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        <div className="lg:col-span-2">{stats && <MonthlyChart data={stats.by_month} />}</div>
        <div>{stats && <TemplateBreakdown data={stats.by_template} />}</div>
      </div>

      <div className="surface-card">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
          <h2 className="section-title">Recent documents</h2>
          <Link to="/documents" className="text-sm text-brand-700 hover:underline inline-flex items-center gap-1">
            View all <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
        {recent.length === 0 ? (
          <div className="px-5 py-10 text-center">
            <FileCheck2 className="w-8 h-8 text-slate-300 mx-auto mb-2" />
            <p className="text-sm text-slate-600">No documents yet.</p>
            <Link to="/home" className="text-sm text-brand-700 hover:underline">Describe your event to create the first ones</Link>
          </div>
        ) : (
          <ul className="divide-y divide-slate-100">
            {recent.slice(0, 6).map((d) => (
              <li key={d.id}>
                <Link to={`/documents/${d.id}`} className="flex items-center justify-between gap-4 px-5 py-3 hover:bg-slate-50">
                  <span className="min-w-0">
                    <span className="block text-sm font-medium text-slate-900 truncate">{d.title}</span>
                    <span className="block text-xs text-slate-500 font-mono">{d.ref_no || '—'}</span>
                  </span>
                  <span className="badge bg-slate-100 text-slate-700 border-slate-200 flex-shrink-0">
                    {STATUS_LABEL[d.status] || d.status}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
};
