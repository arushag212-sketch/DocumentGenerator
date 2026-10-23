import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Users, LayoutTemplate, MessageSquareText, Send, X, ArrowLeft, ArrowRight, FlaskConical } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

/** Fire this event (e.g. from a "Take the tour" button) to show the tour again. */
export const OPEN_TOUR_EVENT = 'clubdocs-open-tour';
export const openWelcomeTour = () => window.dispatchEvent(new Event(OPEN_TOUR_EVENT));

// First card for people in the shared demo club, which every new account joins
const DEMO_STEP = {
  icon: FlaskConical,
  title: 'You are in a demo club',
  text: 'Every new account joins Demo Club SVNIT as an editor so you can try ClubDocs straight away. Create documents and templates freely; it is a shared practice space, not a real club. To work for your own club, register it or ask to join it from the club switcher.',
};

const BASE_STEPS = [
  {
    icon: Users,
    title: 'This is your club’s space',
    text: 'Everything you make here (documents, templates, reference numbers, letterhead) belongs to the club picked in the top-left. Switch clubs there if you are in more than one.',
  },
  {
    icon: LayoutTemplate,
    title: 'Templates are the formats',
    text: 'The SVNIT formats (permission letter, approval note, certificates, bills, minutes) are ready to use. Preview any template, or copy one and change it in the editor.',
  },
  {
    icon: MessageSquareText,
    title: 'Create: describe it once',
    text: 'Open Create and write one line about your event, e.g. “Two-day workshop on 14–15 Oct in the Seminar Hall for 120 students”. ClubDocs drafts the documents; you check the details.',
  },
  {
    icon: Send,
    title: 'Download or send for review',
    text: 'Download PDF or Word, or send a document for review. Once a club admin approves it, the PDF gets a code anyone can verify.',
  },
];

const storageKey = (userId?: string | number) => `clubdocs.tour.v1.${userId ?? 'anon'}`;

function readSeen(key: string): boolean {
  try {
    return window.localStorage.getItem(key) === 'done';
  } catch {
    return true; // storage blocked: do not keep showing the tour
  }
}

function markSeen(key: string) {
  try {
    window.localStorage.setItem(key, 'done');
  } catch {
    /* ignore */
  }
}

/** Four-step introduction shown once after a member first gets into a club; reopen it from Help. */
export const WelcomeTour: React.FC = () => {
  const { user, activeClub } = useAuth();
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState(0);
  const key = storageKey(user?.id);
  const inDemoClub = Boolean(user?.demo_club_slug && activeClub?.slug === user.demo_club_slug);
  const STEPS = inDemoClub ? [DEMO_STEP, ...BASE_STEPS] : BASE_STEPS;

  useEffect(() => {
    if (user && activeClub?.my_role && !readSeen(key)) {
      setStep(0);
      setOpen(true);
    }
  }, [user?.id, activeClub?.my_role]);

  useEffect(() => {
    const show = () => {
      setStep(0);
      setOpen(true);
    };
    window.addEventListener(OPEN_TOUR_EVENT, show);
    return () => window.removeEventListener(OPEN_TOUR_EVENT, show);
  }, []);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') close();
      if (e.key === 'ArrowRight') setStep((s) => Math.min(s + 1, STEPS.length - 1));
      if (e.key === 'ArrowLeft') setStep((s) => Math.max(s - 1, 0));
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);

  const close = () => {
    markSeen(key);
    setOpen(false);
  };

  if (!open) return null;
  const current = STEPS[step];
  const Icon = current.icon;
  const last = step === STEPS.length - 1;

  return (
    <div className="fixed inset-0 z-[70] flex items-end justify-center bg-slate-900/40 p-4 sm:items-center" onClick={close}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="tour-title"
        className="w-full max-w-md overflow-hidden rounded-2xl bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="relative bg-gradient-to-br from-brand-800 to-brand-700 px-6 pb-6 pt-5 text-white">
          <button
            type="button"
            onClick={close}
            className="absolute right-3 top-3 rounded-md p-1.5 text-brand-100 hover:bg-white/10 hover:text-white"
            aria-label="Close the tour"
          >
            <X className="h-4 w-4" />
          </button>
          <p className="text-xs font-medium text-brand-200">
            Welcome to ClubDocs · {step + 1} of {STEPS.length}
          </p>
          <span className="mt-4 flex h-11 w-11 items-center justify-center rounded-xl bg-white/10">
            <Icon className="h-5 w-5 text-svnit-gold" />
          </span>
          <h2 id="tour-title" className="mt-3 text-lg font-semibold">{current.title}</h2>
        </div>

        <div className="px-6 py-5">
          <p className="text-sm leading-relaxed text-slate-600">{current.text}</p>

          <div className="mt-5 flex items-center gap-1.5" aria-hidden="true">
            {STEPS.map((_, i) => (
              <span key={i} className={`h-1.5 rounded-full transition-all ${i === step ? 'w-6 bg-brand-700' : 'w-1.5 bg-slate-200'}`} />
            ))}
          </div>

          <div className="mt-5 flex flex-col-reverse sm:flex-row sm:items-center sm:justify-between gap-3">
            {step === 0 ? (
              <button type="button" onClick={close} className="btn-ghost">Skip</button>
            ) : (
              <button type="button" onClick={() => setStep(step - 1)} className="btn-ghost">
                <ArrowLeft className="h-4 w-4" /> Back
              </button>
            )}
            {last ? (
              <Link to="/home" onClick={close} className="btn-primary">
                Create my first document <ArrowRight className="h-4 w-4" />
              </Link>
            ) : (
              <button type="button" onClick={() => setStep(step + 1)} className="btn-primary" autoFocus>
                Next <ArrowRight className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
