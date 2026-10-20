import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  FilePlus2,
  LayoutTemplate,
  Layers,
  Send,
  Stamp,
  UserPlus,
  BadgeCheck,
  ChevronDown,
  PlayCircle,
  LifeBuoy,
} from 'lucide-react';
import { PageHeader } from '../components/AppShell';
import { openWelcomeTour } from '../components/onboarding/WelcomeTour';

type Guide = { icon: React.ElementType; title: string; steps: React.ReactNode[]; link?: { to: string; label: string } };

const GUIDES: Guide[] = [
  {
    icon: FilePlus2,
    title: 'Create documents for an event',
    steps: [
      'Open Create in the menu.',
      'Describe the event in one line, e.g. “Hackathon on 3–4 Nov in the CSE seminar hall for 200 students”.',
      'ClubDocs picks the documents and drafts them. Check the details on the right; anything it could not find is left for you to fill.',
      'Fix a detail once and it updates every document of the event. Then download PDF or Word.',
    ],
    link: { to: '/home', label: 'Go to Create' },
  },
  {
    icon: LayoutTemplate,
    title: 'Use or change a template',
    steps: [
      'Open Templates. Click Preview to see a template filled with sample data.',
      'Use template starts a document from it. Customize makes a copy for your club that you can change (Edit Draft opens it again later).',
      'In the editor, type {{ to add a field (a part that changes, like the event name), / for blocks, and right-click for formatting.',
      'Publish when it is ready; only published templates can be used to create documents.',
    ],
    link: { to: '/templates', label: 'Go to Templates' },
  },
  {
    icon: Layers,
    title: 'Make many documents at once',
    steps: [
      'Certificates or receipts for a list of people: on Create, click “Make one per row from a spreadsheet”.',
      'Choose the document, then upload a CSV or paste a Google Sheets link shared as “Anyone with the link can view” (up to 300 rows).',
      'Each row becomes its own numbered document; download them together as a ZIP.',
    ],
    link: { to: '/home', label: 'Go to Create' },
  },
  {
    icon: Send,
    title: 'Send a document for review',
    steps: [
      'Open the document from Documents and click Submit for review.',
      'A club admin or owner sees it as “Awaiting review” and can approve it or ask for changes.',
      'Every step is recorded in the document’s activity list.',
    ],
    link: { to: '/documents', label: 'Go to Documents' },
  },
  {
    icon: BadgeCheck,
    title: 'Verify an approved document',
    steps: [
      'Approved PDFs carry a verification code.',
      'Anyone can enter the code at the Verify page (no sign-in needed), and upload the PDF to check it was not changed.',
    ],
    link: { to: '/verify', label: 'Open Verify' },
  },
  {
    icon: Stamp,
    title: 'Change the letterhead (admins)',
    steps: [
      'Open Settings → Club Settings → Letterhead & Logo.',
      'Edit the club name line and subtitle, and the colour. The college logo and your club logo are added automatically.',
      'New documents use the new letterhead; documents already made are not changed.',
    ],
    link: { to: '/settings/club', label: 'Open Settings' },
  },
  {
    icon: UserPlus,
    title: 'Invite members (admins)',
    steps: [
      'Open Members and create an invite link with the role the person should have.',
      'Share the link. They sign in with their SVNIT Google account and join straight away.',
      'People who find your club themselves send a join request, which you approve under Join requests.',
    ],
    link: { to: '/settings/members', label: 'Open Members' },
  },
];

const FAQ: { q: string; a: string }[] = [
  {
    q: 'Why can I only sign in with an @svnit.ac.in account?',
    a: 'ClubDocs is for SVNIT clubs, and official documents should only be made by institute members.',
  },
  {
    q: 'Does the AI make up details?',
    a: 'No. It only uses what you wrote. Missing dates, amounts, venues or names are left blank or asked for, and AI-written text is marked for review.',
  },
  {
    q: 'The first page load took a minute. Is something wrong?',
    a: 'The free server sleeps when nobody uses it and needs up to a minute to wake. After that it is fast.',
  },
  {
    q: 'Who can see my club’s documents?',
    a: 'Only members of your club (and the platform admins). Other clubs cannot see them.',
  },
];

const GuideCard: React.FC<{ guide: Guide; defaultOpen?: boolean }> = ({ guide, defaultOpen }) => {
  const [open, setOpen] = useState(Boolean(defaultOpen));
  const Icon = guide.icon;
  return (
    <div className="surface-card overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className="flex w-full items-center gap-3 px-5 py-4 text-left hover:bg-slate-50"
      >
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-700">
          <Icon className="h-[18px] w-[18px]" />
        </span>
        <span className="flex-1 text-sm font-semibold text-slate-900">{guide.title}</span>
        <ChevronDown className={`h-4 w-4 text-slate-400 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div className="border-t border-slate-100 px-5 pb-5 pt-4">
          <ol className="space-y-2.5">
            {guide.steps.map((step, i) => (
              <li key={i} className="flex gap-3 text-sm text-slate-600">
                <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-slate-100 text-[11px] font-semibold text-slate-600">
                  {i + 1}
                </span>
                <span className="leading-relaxed">{step}</span>
              </li>
            ))}
          </ol>
          {guide.link && (
            <Link to={guide.link.to} className="mt-4 inline-flex text-sm font-medium text-brand-700 hover:underline">
              {guide.link.label} →
            </Link>
          )}
        </div>
      )}
    </div>
  );
};

export const HelpPage: React.FC = () => (
  <div className="mx-auto max-w-3xl px-4 py-8 sm:px-8">
    <PageHeader
      title="Help & guide"
      description="Short how-tos for everything you can do in ClubDocs."
      actions={
        <button type="button" onClick={openWelcomeTour} className="btn-secondary">
          <PlayCircle className="h-4 w-4" />
          Take the tour
        </button>
      }
    />

    <div className="space-y-3">
      {GUIDES.map((g, i) => (
        <GuideCard key={g.title} guide={g} defaultOpen={i === 0} />
      ))}
    </div>

    <h2 className="section-title mb-3 mt-10">Common questions</h2>
    <dl className="surface-card divide-y divide-slate-100">
      {FAQ.map(({ q, a }) => (
        <div key={q} className="px-5 py-4">
          <dt className="text-sm font-medium text-slate-900">{q}</dt>
          <dd className="mt-1 text-sm leading-relaxed text-slate-600">{a}</dd>
        </div>
      ))}
    </dl>

    <p className="mt-8 flex items-center gap-2 text-xs text-slate-500">
      <LifeBuoy className="h-4 w-4" />
      Still stuck? Ask your club admin, or the platform admin who set up ClubDocs for SVNIT.
    </p>
  </div>
);
