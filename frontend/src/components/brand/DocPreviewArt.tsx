import React from 'react';
import { CheckCircle2 } from 'lucide-react';

/**
 * Decorative stack of club documents (a letter in front of a certificate), drawn with CSS so the
 * landing and sign-in pages show what the app produces without loading screenshots.
 */
export const DocPreviewArt: React.FC<{ className?: string }> = ({ className = '' }) => (
  <div className={`relative select-none ${className}`} aria-hidden="true">
    {/* Certificate behind */}
    <div className="absolute -right-3 sm:-right-6 top-6 w-[78%] aspect-[1.414/1] rotate-6 rounded-lg bg-[#fffaf0] shadow-xl ring-1 ring-black/5">
      <div className="absolute inset-2 rounded border-2 border-double border-svnit-gold/60" />
      <div className="flex h-full flex-col items-center justify-center gap-1.5 px-6">
        <div className="h-1.5 w-1/3 rounded-full bg-svnit-gold/50" />
        <div className="h-2.5 w-2/3 rounded-full bg-brand-700/70" />
        <div className="h-1.5 w-1/2 rounded-full bg-slate-300" />
        <div className="mt-2 flex w-2/3 justify-between">
          <div className="h-1 w-1/4 rounded-full bg-slate-300" />
          <div className="h-1 w-1/4 rounded-full bg-slate-300" />
        </div>
      </div>
    </div>

    {/* Letter in front */}
    <div className="relative w-[78%] aspect-[1/1.414] -rotate-2 rounded-lg bg-white shadow-2xl ring-1 ring-black/5 p-[7%]">
      {/* Letterhead */}
      <div className="flex items-center gap-2 border-b-2 border-brand-700 pb-2">
        <img src="/brand/svnit_crest.png" alt="" className="h-6 w-6 object-contain" />
        <div className="flex-1 space-y-1">
          <div className="h-1.5 w-3/4 rounded-full bg-brand-700" />
          <div className="h-1 w-1/2 rounded-full bg-slate-300" />
        </div>
        <div className="h-6 w-6 rounded bg-brand-100" />
      </div>
      <div className="mt-3 flex justify-between">
        <div className="h-1 w-1/3 rounded-full bg-slate-300" />
        <div className="h-1 w-1/5 rounded-full bg-slate-300" />
      </div>
      <div className="mx-auto mt-3 h-1.5 w-1/2 rounded-full bg-slate-700" />
      <div className="mt-3 space-y-1.5">
        {[100, 92, 96, 70].map((w, i) => (
          <div key={i} className="h-1 rounded-full bg-slate-200" style={{ width: `${w}%` }} />
        ))}
      </div>
      <div className="mt-2 flex flex-wrap gap-1">
        <span className="h-2 w-14 rounded bg-brand-100" />
        <span className="h-2 w-10 rounded bg-brand-100" />
      </div>
      <div className="mt-2 space-y-1.5">
        {[96, 88].map((w, i) => (
          <div key={i} className="h-1 rounded-full bg-slate-200" style={{ width: `${w}%` }} />
        ))}
      </div>
      <div className="absolute bottom-[8%] left-[7%] right-[7%] flex justify-between">
        {[0, 1, 2].map((i) => (
          <div key={i} className="w-1/4 space-y-1 border-t border-slate-400 pt-1">
            <div className="h-1 rounded-full bg-slate-300" />
          </div>
        ))}
      </div>
    </div>

    {/* Status chip */}
    <div className="absolute -left-2 sm:-left-3 bottom-10 flex items-center gap-1.5 rounded-full bg-white px-3 py-1.5 text-[11px] font-semibold text-emerald-700 shadow-lg ring-1 ring-black/5">
      <CheckCircle2 className="h-3.5 w-3.5" />
      Approved · ACM/26-27/EVT/014
    </div>
  </div>
);
