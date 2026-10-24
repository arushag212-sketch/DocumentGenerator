import React, { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { Bell, CheckCheck, FileCheck2, FileClock, FilePen, UserPlus } from 'lucide-react';
import { api } from '../../api/client';
import type { AppNotification } from '../../types';

const ICONS: Record<string, React.ElementType> = {
  review_requested: FileClock,
  approved: FileCheck2,
  changes_requested: FilePen,
  join_request: UserPlus,
};

function timeAgo(iso: string): string {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
}

/** The bell: unread count, a list of recent notices, mark read. Checks for new ones every minute. */
export const NotificationBell: React.FC = () => {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<AppNotification[]>([]);
  const [unread, setUnread] = useState(0);
  // Placed against the window: the sidebar would otherwise clip a panel wider than itself
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  const load = useCallback(() => {
    api.notifications
      .list()
      .then((res) => {
        setItems(res.items);
        setUnread(res.unread);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    load();
    const t = window.setInterval(() => {
      if (document.visibilityState === 'visible') load();
    }, 60_000);
    return () => window.clearInterval(t);
  }, [load]);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      const t = e.target as Node;
      if (!buttonRef.current?.contains(t) && !panelRef.current?.contains(t)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false);
    document.addEventListener('mousedown', close);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', close);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const openItem = (n: AppNotification) => {
    setOpen(false);
    if (!n.read) {
      setItems((prev) => prev.map((i) => (i.id === n.id ? { ...i, read: true } : i)));
      setUnread((u) => Math.max(0, u - 1));
      api.notifications.markRead(n.id).catch(() => {});
    }
    if (n.link) navigate(n.link);
  };

  const markAll = () => {
    setItems((prev) => prev.map((i) => ({ ...i, read: true })));
    setUnread(0);
    api.notifications.markAllRead().catch(() => {});
  };

  return (
    <>
      <button
        type="button"
        ref={buttonRef}
        onClick={() => {
          if (!open) {
            const r = buttonRef.current?.getBoundingClientRect();
            if (r) setPos({ top: r.bottom + 8, left: Math.min(r.left, window.innerWidth - 400) });
            load();
          }
          setOpen((v) => !v);
        }}
        className="relative flex h-11 w-11 lg:h-9 lg:w-9 shrink-0 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-900 transition-colors"
        aria-label={unread ? `Notifications, ${unread} unread` : 'Notifications'}
        aria-haspopup="dialog"
        aria-expanded={open}
      >
        <Bell className="h-[18px] w-[18px]" />
        {unread > 0 && (
          <span className="absolute right-1 top-1 flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-amber-500 px-1 text-[10px] font-bold text-white ring-2 ring-white">
            {unread > 9 ? '9+' : unread}
          </span>
        )}
      </button>

      {open &&
        createPortal(
          <div
            ref={panelRef}
            role="dialog"
            aria-label="Notifications"
            className="fixed left-3 right-3 top-14 z-[60] rounded-xl border border-slate-200 bg-white shadow-xl sm:right-auto sm:w-96"
            style={pos && window.innerWidth >= 640 ? { top: pos.top, left: Math.max(12, pos.left) } : undefined}
          >
            <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
              <p className="section-title">Notifications</p>
              {unread > 0 && (
                <button type="button" onClick={markAll} className="btn-ghost !px-2 !py-1 text-xs">
                  <CheckCheck className="h-4 w-4" /> Mark all read
                </button>
              )}
            </div>
            {items.length === 0 ? (
              <p className="px-4 py-10 text-center text-sm text-slate-500">You're all caught up.</p>
            ) : (
              <ul className="max-h-[60vh] divide-y divide-slate-100 overflow-y-auto">
                {items.map((n) => {
                  const Icon = ICONS[n.kind] || Bell;
                  return (
                    <li key={n.id}>
                      <button
                        type="button"
                        onClick={() => openItem(n)}
                        className={`flex w-full items-start gap-3 px-4 py-3 text-left transition-colors hover:bg-slate-50 ${n.read ? '' : 'bg-brand-50/60'}`}
                      >
                        <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-700">
                          <Icon className="h-4 w-4" />
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className={`block text-sm ${n.read ? 'text-slate-700' : 'font-semibold text-slate-900'}`}>{n.title}</span>
                          {n.body && <span className="mt-0.5 block line-clamp-2 text-xs text-slate-500">{n.body}</span>}
                          <span className="mt-1 block text-[11px] text-slate-400">{timeAgo(n.created_at)}</span>
                        </span>
                        {!n.read && <span className="mt-2 h-2 w-2 shrink-0 rounded-full bg-amber-500" aria-label="Unread" />}
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>,
          document.body,
        )}
    </>
  );
};
