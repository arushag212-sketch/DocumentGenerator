import React, { useEffect, useState } from 'react';
import { SERVER_WAKING_EVENT } from '../../api/client';

/** Shown while the sleeping free-tier server starts up, so a slow first load is not mistaken for an error. */
export const ServerWakeBanner: React.FC = () => {
  const [waking, setWaking] = useState(false);

  useEffect(() => {
    const onEvent = (e: Event) => setWaking(Boolean((e as CustomEvent<{ waking: boolean }>).detail?.waking));
    window.addEventListener(SERVER_WAKING_EVENT, onEvent);
    return () => window.removeEventListener(SERVER_WAKING_EVENT, onEvent);
  }, []);

  if (!waking) return null;
  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed top-3 left-1/2 -translate-x-1/2 z-[100] flex items-center gap-2.5 rounded-full bg-slate-900 text-white text-xs font-medium px-4 py-2 shadow-lg"
    >
      <span className="h-3.5 w-3.5 rounded-full border-2 border-white/40 border-t-white animate-spin" aria-hidden="true" />
      Waking up the server… this can take up to a minute.
    </div>
  );
};
