import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { FilePlus2, LayoutTemplate, FileCheck2, Clock3, Files, Hourglass, ArrowRight, LifeBuoy, ChevronRight } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import { ClubAnalytics } from '../types';
import { GettingStarted } from '../components/onboarding/GettingStarted';

const STATUS_STYLE: Record<string, string> = {
  ready: 'bg-slate-100 text-slate-700 border-slate-200',
  submitted: 'bg-amber-50 text-amber-800 border-amber-200',
  approved: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  changes_requested: 'bg-red-50 text-red-700 border-red-200',
  draft: 'bg-slate-100 text-slate-600 border-slate-200',
  finalized: 'bg-emerald-50 text-emerald-700 border-emerald-200',
};

function greeting(): string {
  const h = new Date().getHours();
  return h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening';
}

const STATUS_LABEL: Record<string, string> = {
  ready: 'Ready',
  submitted: 'Awaiting review',
  approved: 'Approved',
  changes_requested: 'Changes requested',
  draft: 'Draft',
  finalized: 'Finalized',
};

function StatTile({
  label,
  value,
  hint,
  icon: Icon,
  tone = 'brand',
  to,
}: {
  label: string;
  value: React.ReactNode;
  hint?: string;
  icon: React.ElementType;
  tone?: 'brand' | 'amber' | 'emerald' | 'slate';
  to?: string;
}) {
  const chip = {
    brand: 'bg-brand-50 text-brand-700',
    amber: 'bg-amber-50 text-amber-700',
    emerald: 'bg-emerald-50 text-emerald-700',
    slate: 'bg-slate-100 text-slate-600',
  }[tone];
  const body = (
    <>
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm text-slate-500">{label}</p>
        <span className={`flex h-8 w-8 items-center justify-center rounded-lg ${chip}`}>
          <Icon className="w-4 h-4" aria-hidden />
        </span>
      </div>
      <p className="mt-1 text-2xl font-semibold text-slate-900 tabular-nums">{value}</p>
      {hint && <p className="mt-0.5 text-xs text-slate-500">{hint}</p>}
    </>
  );
  return to ? (
    <Link to={to} className="surface-card block p-4 transition-shadow hover:shadow-md focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500">
      {body}
    </Link>
  ) : (
    <div className="surface-card p-4">{body}</div>
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
        <div className="overflow-x-auto pb-2">
          <div className="relative min-w-[320px]">
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

  const firstName = (user?.name || '').split(' ')[0];

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-8 py-8">
      <section className="relative mb-6 overflow-hidden rounded-2xl bg-gradient-to-br from-brand-800 via-brand-700 to-brand-600 px-6 py-7 text-white sm:px-8">
        <div className="pointer-events-none absolute -right-16 -top-20 h-64 w-64 rounded-full bg-white/5" aria-hidden="true" />
        <div className="pointer-events-none absolute -bottom-24 right-24 h-56 w-56 rounded-full bg-svnit-gold/10" aria-hidden="true" />
        <div className="relative flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-sm text-brand-100">{greeting()}{firstName ? ',' : ''}</p>
            <h1 className="mt-0.5 text-2xl font-semibold tracking-tight sm:text-3xl">{firstName || 'Welcome'}</h1>
            <p className="mt-1.5 text-sm text-brand-100">
              {activeClub?.name}
              {stats && stats.awaiting_review > 0 ? ` · ${stats.awaiting_review} waiting for review` : ''}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link
              to="/home"
              className="inline-flex items-center gap-2 rounded-lg bg-white px-4 py-2 text-sm font-semibold text-brand-800 shadow-sm transition-colors hover:bg-brand-50"
            >
              <FilePlus2 className="w-4 h-4" />
              Create documents
            </Link>
            <Link
              to="/templates"
              className="inline-flex items-center gap-2 rounded-lg bg-white/10 px-4 py-2 text-sm font-semibold text-white ring-1 ring-white/20 transition-colors hover:bg-white/20"
            >
              <LayoutTemplate className="w-4 h-4" />
              Templates
            </Link>
          </div>
        </div>
      </section>

      {error && <p className="text-sm text-red-600 mb-4">{error}</p>}

      <GettingStarted stats={stats} />

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 mb-6">
        <StatTile label="This month" value={stats?.documents_this_month ?? '–'} hint="documents generated" icon={FilePlus2} />
        <StatTile label="All documents" value={stats?.documents_total ?? '–'} hint={stats ? `${stats.events_total} events` : undefined} icon={Files} tone="slate" to="/documents" />
        <StatTile label="Awaiting review" value={stats?.awaiting_review ?? '–'} hint={stats ? `${stats.approvals} approved` : undefined} icon={Hourglass} tone="amber" to="/documents?status=submitted" />
        <StatTile label="Time saved" value={stats ? `${stats.hours_saved} h` : '–'} hint="estimated, 25 min per document" icon={Clock3} tone="emerald" />
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
                <Link to={`/documents/${d.id}`} className="group flex items-center justify-between gap-4 px-5 py-3 hover:bg-slate-50">
                  <span className="flex min-w-0 items-center gap-3">
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-500 group-hover:bg-brand-50 group-hover:text-brand-700">
                      <FileCheck2 className="w-4 h-4" />
                    </span>
                    <span className="min-w-0">
                      <span className="block text-sm font-medium text-slate-900 truncate">{d.title}</span>
                      <span className="block text-xs text-slate-500 font-mono">{d.ref_no || 'No reference number'}</span>
                    </span>
                  </span>
                  <span className="flex flex-shrink-0 items-center gap-2">
                    <span className={`badge ${STATUS_STYLE[d.status] || STATUS_STYLE.draft}`}>{STATUS_LABEL[d.status] || d.status}</span>
                    <ChevronRight className="w-4 h-4 text-slate-300 group-hover:text-slate-500" />
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>

      <Link to="/help" className="mt-6 flex items-center gap-2 text-sm text-slate-500 hover:text-brand-700">
        <LifeBuoy className="w-4 h-4" />
        New to ClubDocs? Read the short how-to guides
      </Link>
    </div>
  );
};
