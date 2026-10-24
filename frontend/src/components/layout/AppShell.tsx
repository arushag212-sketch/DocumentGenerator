import React, { useEffect, useRef, useState } from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  FilePlus2,
  Files,
  LayoutTemplate,
  Users,
  UserPlus,
  Settings,
  LogOut,
  ChevronsUpDown,
  Check,
  Menu,
  X,
  Plus,
  LifeBuoy,
} from 'lucide-react';
import { WelcomeTour } from '../onboarding/WelcomeTour';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../api/client';

type NavItem = { to: string; label: string; icon: React.ElementType; badge?: number; match?: string[] };

function ClubMark({ clubId, name, size = 32 }: { clubId?: string | number; name?: string; size?: number }) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [clubId]);
  const initials = (name || '?').replace(/[^A-Za-z ]/g, '').split(' ').filter(Boolean).slice(0, 2).map((w) => w[0]).join('').toUpperCase();
  if (clubId && !failed) {
    return (
      <img
        src={`/api/v1/clubs/${clubId}/public-logo`}
        alt=""
        onError={() => setFailed(true)}
        className="rounded-md bg-white object-contain border border-slate-200"
        style={{ width: size, height: size }}
      />
    );
  }
  return (
    <span
      className="rounded-md bg-brand-700 text-white text-xs font-semibold flex items-center justify-center"
      style={{ width: size, height: size }}
    >
      {initials || '?'}
    </span>
  );
}

function ClubSwitcher() {
  const { clubs, activeClub, setActiveClubId, user } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const close = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, []);

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-haspopup="listbox"
        aria-expanded={open}
        className="w-full flex items-center gap-2.5 p-2 rounded-lg hover:bg-slate-100 text-left transition-colors"
      >
        <ClubMark clubId={activeClub?.id} name={activeClub?.name} />
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-semibold text-slate-900 truncate">{activeClub?.short_name || activeClub?.name || 'Choose a club'}</span>
          <span className="block text-xs text-slate-500 truncate capitalize">
            {user?.is_platform_admin ? 'Platform admin' : activeClub?.my_role || 'Pending approval'}
          </span>
        </span>
        <ChevronsUpDown className="w-4 h-4 text-slate-400 flex-shrink-0" />
      </button>

      {open && (
        <div className="absolute left-0 right-0 mt-1 bg-white border border-slate-200 rounded-lg shadow-lg z-50 py-1" role="listbox">
          <div className="max-h-72 overflow-y-auto">
            {clubs.map((c) => (
              <button
                key={c.id}
                type="button"
                role="option"
                aria-selected={String(c.id) === String(activeClub?.id)}
                onClick={() => {
                  setActiveClubId(c.id);
                  setOpen(false);
                }}
                className="w-full flex items-center gap-2.5 px-2.5 py-2.5 lg:py-2 min-h-[44px] lg:min-h-0 text-left hover:bg-slate-50"
              >
                <ClubMark clubId={c.id} name={c.name} size={24} />
                <span className="min-w-0 flex-1">
                  <span className="block text-sm text-slate-800 truncate">{c.name}</span>
                  {!c.my_role && !user?.is_platform_admin && <span className="block text-xs text-amber-600">Pending approval</span>}
                </span>
                {String(c.id) === String(activeClub?.id) && <Check className="w-4 h-4 text-brand-700" />}
              </button>
            ))}
          </div>
          <div className="border-t border-slate-100 mt-1 pt-1">
            <Link
              to="/onboarding/club"
              onClick={() => setOpen(false)}
              className="flex items-center gap-2 px-2.5 py-2.5 lg:py-2 min-h-[44px] lg:min-h-0 text-sm text-slate-700 hover:bg-slate-50"
            >
              <Plus className="w-4 h-4" />
              Join or register a club
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}

export const AppShell: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, activeClub, logout } = useAuth();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [pendingCount, setPendingCount] = useState(0);

  const hasClubAccess = Boolean(user?.is_platform_admin || activeClub?.my_role);
  const isClubAdmin = Boolean(user?.is_platform_admin || activeClub?.my_role === 'owner' || activeClub?.my_role === 'admin');

  useEffect(() => setMobileOpen(false), [location.pathname]);

  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth >= 1024) {
        setMobileOpen(false);
      }
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  useEffect(() => {
    if (!mobileOpen) return;
    const originalOverflow = document.body.style.overflow;
    const originalTouchAction = document.body.style.touchAction;
    document.body.style.overflow = 'hidden';
    document.body.style.touchAction = 'none';

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMobileOpen(false);
    };
    window.addEventListener('keydown', handleKeyDown);

    return () => {
      document.body.style.overflow = originalOverflow;
      document.body.style.touchAction = originalTouchAction;
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [mobileOpen]);

  useEffect(() => {
    if (!activeClub || !isClubAdmin) {
      setPendingCount(0);
      return;
    }
    api.clubs
      .listJoinRequests(activeClub.id)
      .then((reqs) => setPendingCount((reqs || []).filter((r) => r.status === 'pending').length))
      .catch(() => setPendingCount(0));
  }, [activeClub?.id, isClubAdmin, location.pathname]);

  const groups: { label?: string; items: NavItem[] }[] = hasClubAccess
    ? [
        {
          items: [
            { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
            { to: '/home', label: 'Create', icon: FilePlus2, match: ['/home', '/documents/new'] },
            { to: '/documents', label: 'Documents', icon: Files },
            { to: '/templates', label: 'Templates', icon: LayoutTemplate },
          ],
        },
        {
          label: 'Club',
          items: [
            { to: '/settings/members', label: 'Members', icon: Users },
            ...(isClubAdmin ? [{ to: '/join-requests', label: 'Join requests', icon: UserPlus, badge: pendingCount }] : []),
            { to: '/settings/club', label: 'Settings', icon: Settings, match: ['/settings/club', '/settings/people', '/settings/audit'] },
          ],
        },
        {
          items: [{ to: '/help', label: 'Help & guide', icon: LifeBuoy }],
        },
      ]
    : [];

  const isActive = (item: NavItem) =>
    (item.match || [item.to]).some((m) => location.pathname === m || (m !== '/home' && location.pathname.startsWith(m + '/')));

  const initials = (user?.name || user?.email || '?')
    .split(' ')
    .map((w) => w[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();
  const canCreate = Boolean(user?.is_platform_admin || (activeClub?.my_role && activeClub.my_role !== 'viewer'));

  const sidebar = (
    <div className="flex flex-col h-full">
      <div className="px-3 pt-4 pb-3 space-y-3">
        <Link to="/dashboard" className="flex items-center gap-2.5 px-2">
          <img src="/brand/clubdocs_logo.svg" alt="" className="h-8 w-8 rounded-lg" />
          <span className="leading-tight">
            <span className="block text-sm font-semibold text-slate-900">ClubDocs</span>
            <span className="block text-[11px] text-slate-400">SVNIT Surat</span>
          </span>
        </Link>
        <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-1">
          <ClubSwitcher />
        </div>
        {hasClubAccess && canCreate && (
          <Link to="/home" className="btn-primary w-full justify-center min-h-[44px] lg:min-h-0 flex items-center gap-2">
            <FilePlus2 className="w-4 h-4" />
            New document
          </Link>
        )}
      </div>

      <nav className="flex-1 overflow-y-auto px-3 pb-3 space-y-5" aria-label="Main">
        {groups.map((group, gi) => (
          <div key={gi}>
            {group.label && <p className="px-2.5 mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-400">{group.label}</p>}
            <ul className="space-y-1 lg:space-y-0.5">
              {group.items.map((item) => {
                const active = isActive(item);
                const Icon = item.icon;
                return (
                  <li key={item.to}>
                    <NavLink
                      to={item.to}
                      aria-current={active ? 'page' : undefined}
                      className={`group flex items-center gap-2.5 px-2.5 py-2.5 lg:py-2 min-h-[44px] lg:min-h-0 rounded-lg text-sm transition-colors ${
                        active
                          ? 'bg-slate-100 text-slate-900 font-medium'
                          : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                      }`}
                    >
                      <Icon className={`w-[18px] h-[18px] transition-colors ${active ? 'text-brand-700' : 'text-slate-400 group-hover:text-slate-600'}`} />
                      <span className="flex-1">{item.label}</span>
                      {!!item.badge && (
                        <span className="min-w-[1.25rem] px-1.5 text-center text-xs font-semibold rounded-full bg-amber-100 text-amber-800">
                          {item.badge}
                        </span>
                      )}
                    </NavLink>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      <div className="border-t border-slate-200 p-3">
        <div className="flex items-center gap-1">
          <NavLink
            to="/profile"
            title="Your profile"
            className={({ isActive: onProfile }) =>
              `flex min-w-0 flex-1 items-center gap-2.5 rounded-lg px-2 py-2 lg:py-1.5 min-h-[44px] lg:min-h-0 transition-colors ${onProfile ? 'bg-brand-50' : 'hover:bg-slate-100'}`
            }
          >
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-brand-600 to-brand-800 text-xs font-semibold text-white">
              {initials}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-sm font-medium text-slate-800 truncate">{user?.name}</span>
              <span className="block text-xs text-slate-500 truncate">View profile</span>
            </span>
          </NavLink>
          <button
            type="button"
            onClick={logout}
            className="btn-ghost !p-0 min-h-[44px] min-w-[44px] lg:min-h-0 lg:min-w-0 lg:!p-2 flex items-center justify-center rounded-lg"
            title="Sign out"
            aria-label="Sign out"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen flex bg-slate-50">
      {/* Desktop sidebar */}
      <aside className="hidden lg:block w-64 flex-shrink-0 border-r border-slate-200 bg-white sticky top-0 h-screen">
        {sidebar}
      </aside>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div
          className="lg:hidden fixed inset-0 z-50 flex"
          role="dialog"
          aria-modal="true"
          aria-label="Navigation menu"
        >
          <div
            className="absolute inset-0 bg-slate-900/40 backdrop-blur-xs transition-opacity"
            onClick={() => setMobileOpen(false)}
          />
          <aside className="relative w-72 max-w-[calc(100vw-3rem)] bg-white h-full shadow-2xl flex flex-col">
            <button
              type="button"
              onClick={() => setMobileOpen(false)}
              className="absolute top-2 right-2 z-10 btn-ghost !p-0 min-h-[44px] min-w-[44px] flex items-center justify-center rounded-lg"
              aria-label="Close menu"
            >
              <X className="w-5 h-5 text-slate-500" />
            </button>
            {sidebar}
          </aside>
        </div>
      )}

      <div className="flex-1 min-w-0 flex flex-col">
        <header className="lg:hidden sticky top-0 z-40 flex items-center gap-3 h-14 px-4 bg-white/95 backdrop-blur border-b border-slate-200">
          <button
            type="button"
            onClick={() => setMobileOpen(true)}
            className="btn-ghost !p-0 min-h-[44px] min-w-[44px] flex items-center justify-center -ml-2 rounded-lg"
            aria-label="Open menu"
          >
            <Menu className="w-6 h-6 text-slate-700" />
          </button>
          <span className="flex-1 text-sm font-semibold text-slate-900 truncate">{activeClub?.name || 'ClubDocs'}</span>
          <Link
            to="/profile"
            aria-label="Your profile"
            className="min-h-[44px] min-w-[44px] flex items-center justify-center -mr-2 rounded-lg"
          >
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-brand-600 to-brand-800 text-xs font-semibold text-white">
              {initials}
            </span>
          </Link>
        </header>
        <main className="flex-1 min-w-0 overflow-x-hidden">{children}</main>
      </div>
      <WelcomeTour />
    </div>
  );
};

/** Standard page header: title, optional description and actions. */
export const PageHeader: React.FC<{ title: string; description?: React.ReactNode; actions?: React.ReactNode }> = ({
  title,
  description,
  actions,
}) => (
  <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3 mb-6">
    <div>
      <h1 className="page-title">{title}</h1>
      {description && <p className="page-subtitle">{description}</p>}
    </div>
    {actions && <div className="flex items-center gap-2 flex-wrap">{actions}</div>}
  </div>
);
