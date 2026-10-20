import React from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowRight,
  FileSignature,
  LayoutTemplate,
  Layers,
  MessageSquareText,
  ListChecks,
  Download,
  ShieldCheck,
  Hash,
  BadgeCheck,
} from 'lucide-react';
import { DocPreviewArt } from '../components/brand/DocPreviewArt';

/** Google "G" mark, inline so the page loads nothing from other sites. */
const GoogleG: React.FC<{ className?: string }> = ({ className }) => (
  <svg viewBox="0 0 48 48" className={className} aria-hidden="true">
    <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z" />
    <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z" />
    <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z" />
    <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z" />
  </svg>
);

const FEATURES = [
  {
    icon: MessageSquareText,
    title: 'Describe it once',
    text: 'Write one line about your event. ClubDocs picks the letters, notices and certificates it needs and fills them in.',
  },
  {
    icon: LayoutTemplate,
    title: 'Templates that look official',
    text: 'SVNIT formats out of the box, your club letterhead on every page, and a simple editor for your own designs.',
  },
  {
    icon: Layers,
    title: 'Bulk in one go',
    text: 'Participation certificates or receipts for a whole list of names from a sheet, numbered and ready to print.',
  },
];

const STEPS = [
  { icon: MessageSquareText, title: 'Describe', text: '“Two-day web dev workshop on 14–15 Oct in the Seminar Hall for 120 students.”' },
  { icon: ListChecks, title: 'Check', text: 'Review the drafted details. Anything missing is asked for, never made up.' },
  { icon: Download, title: 'Download', text: 'PDF or Word with your letterhead and reference number, or send it for approval.' },
];

const TRUST = [
  { icon: ShieldCheck, text: 'Only @svnit.ac.in accounts' },
  { icon: Hash, text: 'Automatic reference numbers' },
  { icon: BadgeCheck, text: 'Approved PDFs can be verified' },
];

export const LandingPage: React.FC = () => (
  <div className="min-h-screen bg-white text-slate-900">
    {/* Top bar */}
    <header className="sticky top-0 z-20 border-b border-slate-100 bg-white/90 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
        <Link to="/" className="flex items-center gap-2.5">
          <img src="/brand/svnit_crest.png" alt="" className="h-9 w-9 object-contain" />
          <span>
            <span className="block text-base font-semibold leading-tight">ClubDocs</span>
            <span className="block text-[11px] leading-tight text-slate-500">SVNIT Surat</span>
          </span>
        </Link>
        <nav className="flex items-center gap-2">
          <Link to="/verify" className="btn-ghost hidden sm:inline-flex">Verify a document</Link>
          <Link to="/login" className="btn-primary">
            Sign in
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </nav>
      </div>
    </header>

    {/* Hero */}
    <section className="relative overflow-hidden bg-gradient-to-br from-brand-900 via-brand-800 to-brand-700 text-white">
      <div className="pointer-events-none absolute -right-32 -top-32 h-[28rem] w-[28rem] rounded-full bg-white/5" aria-hidden="true" />
      <div className="pointer-events-none absolute -bottom-40 left-1/3 h-96 w-96 rounded-full bg-svnit-gold/10" aria-hidden="true" />
      <div className="relative mx-auto grid max-w-6xl items-center gap-12 px-4 py-16 sm:px-6 md:grid-cols-[1.2fr_1fr] md:py-24">
        <div>
          <p className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-xs font-medium text-brand-100">
            <FileSignature className="h-3.5 w-3.5 text-svnit-gold" />
            For SVNIT student clubs and chapters
          </p>
          <h1 className="mt-5 text-4xl font-semibold leading-[1.1] tracking-tight sm:text-5xl">
            Official club documents,
            <br />
            <span className="text-svnit-gold">ready in minutes.</span>
          </h1>
          <p className="mt-5 max-w-xl text-base leading-relaxed text-brand-100 sm:text-lg">
            Permission letters, approval notes, certificates, bills and minutes, on your club letterhead and correctly
            numbered. Describe the event; ClubDocs does the paperwork.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Link
              to="/login"
              className="inline-flex items-center gap-2 rounded-lg bg-white px-5 py-3 text-sm font-semibold text-brand-800 shadow-sm transition-colors hover:bg-brand-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-brand-800"
            >
              <GoogleG className="h-4 w-4" />
              Sign in with your SVNIT email
            </Link>
            <a href="#how" className="inline-flex items-center gap-1.5 px-2 py-3 text-sm font-medium text-brand-100 hover:text-white">
              See how it works
              <ArrowRight className="h-3.5 w-3.5" />
            </a>
          </div>
          <ul className="mt-10 flex flex-wrap gap-x-6 gap-y-2 text-xs text-brand-200">
            {TRUST.map(({ icon: Icon, text }) => (
              <li key={text} className="flex items-center gap-1.5">
                <Icon className="h-3.5 w-3.5 text-svnit-gold" />
                {text}
              </li>
            ))}
          </ul>
        </div>
        <div className="flex justify-center md:justify-end">
          <DocPreviewArt className="w-64 sm:w-72" />
        </div>
      </div>
    </section>

    {/* Features */}
    <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6 md:py-20">
      <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">Less typing, fewer mistakes</h2>
      <p className="mt-2 max-w-2xl text-slate-500">
        Every club writes the same documents for every event. ClubDocs keeps your details, formats and numbering in one place.
      </p>
      <div className="mt-10 grid gap-5 md:grid-cols-3">
        {FEATURES.map(({ icon: Icon, title, text }) => (
          <div key={title} className="surface-card p-6 transition-shadow hover:shadow-md">
            <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-50 text-brand-700">
              <Icon className="h-5 w-5" />
            </span>
            <h3 className="mt-4 font-semibold">{title}</h3>
            <p className="mt-1.5 text-sm leading-relaxed text-slate-600">{text}</p>
          </div>
        ))}
      </div>
    </section>

    {/* How it works */}
    <section id="how" className="border-y border-slate-100 bg-slate-50">
      <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6 md:py-20">
        <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">How it works</h2>
        <ol className="mt-10 grid gap-8 md:grid-cols-3">
          {STEPS.map(({ icon: Icon, title, text }, i) => (
            <li key={title} className="relative">
              <div className="flex items-center gap-3">
                <span className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-700 text-sm font-semibold text-white">
                  {i + 1}
                </span>
                <Icon className="h-5 w-5 text-brand-600" aria-hidden="true" />
                <h3 className="font-semibold">{title}</h3>
              </div>
              <p className="mt-3 text-sm leading-relaxed text-slate-600">{text}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>

    {/* Closing call to action */}
    <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
      <div className="flex flex-col items-start justify-between gap-6 rounded-2xl bg-brand-800 px-8 py-10 text-white md:flex-row md:items-center">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">Ready for your next event?</h2>
          <p className="mt-1.5 text-brand-100">Sign in with your SVNIT Google account. Your club can invite you, or you can start one.</p>
        </div>
        <Link
          to="/login"
          className="inline-flex shrink-0 items-center gap-2 rounded-lg bg-svnit-gold px-5 py-3 text-sm font-semibold text-brand-900 transition-colors hover:bg-[#d4ab3a]"
        >
          Get started
          <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    </section>

    <footer className="border-t border-slate-100">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-3 px-4 py-6 text-xs text-slate-500 sm:flex-row sm:px-6">
        <p>ClubDocs · Sardar Vallabhbhai National Institute of Technology, Surat</p>
        <nav className="flex gap-4">
          <Link to="/privacy" className="hover:text-slate-800">Privacy</Link>
          <Link to="/terms" className="hover:text-slate-800">Terms</Link>
          <Link to="/verify" className="hover:text-slate-800">Verify a document</Link>
        </nav>
      </div>
    </footer>
  </div>
);
