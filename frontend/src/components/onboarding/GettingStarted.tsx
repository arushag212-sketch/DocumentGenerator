import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { CheckCircle2, Circle, X, ArrowRight, PlayCircle } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../api/client';
import { ClubAnalytics } from '../../types';
import { openWelcomeTour } from './WelcomeTour';

type Step = { key: string; label: string; hint: string; to: string; done: boolean };

const dismissKey = (clubId: string | number) => `clubdocs.getting-started.dismissed.${clubId}`;
const VISITED_TEMPLATES_KEY = 'clubdocs.getting-started.visited-templates';

/** Called by the Templates page so the "look through the templates" step can be ticked. */
export function markTemplatesVisited() {
  try {
    window.localStorage.setItem(VISITED_TEMPLATES_KEY, '1');
  } catch {
    /* ignore */
  }
}

const SEEN_LETTERHEAD_KEY = 'clubdocs.getting-started.seen-letterhead';

/** Called when the letterhead settings are opened, so checking it counts even if the default is kept. */
export function markLetterheadSeen() {
  try {
    window.localStorage.setItem(SEEN_LETTERHEAD_KEY, '1');
  } catch {
    /* ignore */
  }
}

function seenLetterhead(): boolean {
  try {
    return window.localStorage.getItem(SEEN_LETTERHEAD_KEY) === '1';
  } catch {
    return false;
  }
}

function visitedTemplates(): boolean {
  try {
    return window.localStorage.getItem(VISITED_TEMPLATES_KEY) === '1';
  } catch {
    return false;
  }
}

function isDismissed(clubId: string | number): boolean {
  try {
    return window.localStorage.getItem(dismissKey(clubId)) === '1';
  } catch {
    return false;
  }
}

/**
 * First steps for a club, ticked off from real data (documents made, reviews, members, letterhead).
 * Disappears when everything is done or the member hides it.
 */
export const GettingStarted: React.FC<{ stats: ClubAnalytics | null }> = ({ stats }) => {
  const { activeClub, user } = useAuth();
  const [memberCount, setMemberCount] = useState<number | null>(null);
  // Whether any document can be submitted yet (otherwise the review step points to Create)
  const [hasReadyDoc, setHasReadyDoc] = useState(false);
  const [hidden, setHidden] = useState(true);

  const isAdmin = Boolean(user?.is_platform_admin || activeClub?.my_role === 'owner' || activeClub?.my_role === 'admin');

  useEffect(() => {
    if (!activeClub) return;
    setHidden(isDismissed(activeClub.id));
    setMemberCount(null);
    setHasReadyDoc(false);
    api.documents
      .list(activeClub.id, { status: 'ready', page: 1, page_size: 1 })
      .then((res: any) => setHasReadyDoc((res.items || res || []).length > 0))
      .catch(() => setHasReadyDoc(false));
    if (isAdmin) {
      api.clubs
        .getMembers(activeClub.id)
        .then((m) => setMemberCount(m.length))
        .catch(() => setMemberCount(null));
    }
  }, [activeClub?.id, isAdmin]);

  if (!activeClub || !stats || hidden) return null;

  const settings = activeClub.settings || {};
  const steps: Step[] = [
    {
      key: 'templates',
      label: 'Look through the templates',
      hint: 'Preview the SVNIT formats your club can use.',
      to: '/templates',
      done: visitedTemplates() || stats.documents_total > 0,
    },
    {
      key: 'first-document',
      label: 'Create your first document',
      hint: 'Describe an event in one line; ClubDocs drafts the rest.',
      to: '/home',
      done: stats.documents_total > 0,
    },
    {
      key: 'review',
      label: 'Send a document for review',
      hint: hasReadyDoc
        ? 'Pick one of your documents, then click “Submit for review”; an admin approves it.'
        : 'Create a document first, then open it and click “Submit for review”.',
      to: hasReadyDoc ? '/documents?review=1' : '/home',
      done: stats.awaiting_review + stats.approvals > 0,
    },
    ...(isAdmin
      ? [
          {
            key: 'letterhead',
            label: 'Check your letterhead',
            hint: 'Club name and subtitle printed at the top of every page.',
            to: '/settings/club?tab=letterheads',
            done: seenLetterhead() || Boolean(settings.letterhead_title || settings.letterhead_subtitle),
          },
          {
            key: 'invite',
            label: 'Invite your team',
            hint: 'Send an invite link so other members can join.',
            to: '/settings/members',
            done: (memberCount ?? 0) > 1,
          },
        ]
      : []),
  ];

  const doneCount = steps.filter((s) => s.done).length;
  if (doneCount === steps.length) return null;

  const hide = () => {
    try {
      window.localStorage.setItem(dismissKey(activeClub.id), '1');
    } catch {
      /* ignore */
    }
    setHidden(true);
  };

  return (
    <section className="surface-card mb-6 overflow-hidden" aria-labelledby="getting-started-title">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 sm:gap-4 border-b border-slate-100 px-4 sm:px-5 py-3 sm:py-4">
        <div>
          <h2 id="getting-started-title" className="section-title">Getting started</h2>
          <p className="mt-0.5 text-xs text-slate-500">
            {doneCount} of {steps.length} done
          </p>
        </div>
        <div className="flex items-center gap-1">
          <button type="button" onClick={openWelcomeTour} className="btn-ghost btn-sm">
            <PlayCircle className="h-4 w-4" />
            Take the tour
          </button>
          <button type="button" onClick={hide} className="btn-icon" aria-label="Hide getting started" title="Hide">
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>
      <div className="h-1 bg-slate-100" aria-hidden="true">
        <div className="h-1 bg-brand-600 transition-all" style={{ width: `${(doneCount / steps.length) * 100}%` }} />
      </div>
      {/* Only the steps still to do; finished ones are summed up in the count above */}
      <ol className="divide-y divide-slate-100">
        {steps
          .filter((s) => !s.done)
          .map((s) => (
            <li key={s.key}>
              <Link to={s.to} className="group flex items-center gap-3 px-5 py-3 hover:bg-slate-50">
                <Circle className="h-5 w-5 shrink-0 text-slate-300" aria-label="Not done" />
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-medium text-slate-900">{s.label}</span>
                  <span className="block text-xs text-slate-500">{s.hint}</span>
                </span>
                <ArrowRight className="h-4 w-4 shrink-0 text-slate-300 transition-colors group-hover:text-brand-700" />
              </Link>
            </li>
          ))}
      </ol>
      {doneCount > 0 && (
        <p className="flex items-center gap-1.5 border-t border-slate-100 px-5 py-2.5 text-xs text-slate-500">
          <CheckCircle2 className="h-4 w-4 text-emerald-600" aria-hidden="true" />
          Done: {steps.filter((s) => s.done).map((s) => s.label).join(' · ')}
        </p>
      )}
    </section>
  );
};
