import React, { useState, useEffect } from 'react';
import { NavLink, Link, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import { LogOut, ChevronDown, Building2, UserCircle, UserPlus } from 'lucide-react';

interface HeaderProps {
  memberCount?: number;
  onOpenClubModal?: () => void;
}

export const Header: React.FC<HeaderProps> = ({ onOpenClubModal }) => {
  const { user, clubs, activeClub, setActiveClubId, logout } = useAuth();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [pendingCount, setPendingCount] = useState<number>(0);
  const location = useLocation();

  const isClubAdmin =
    user?.is_platform_admin ||
    activeClub?.my_role === 'owner' ||
    activeClub?.my_role === 'admin';

  useEffect(() => {
    if (activeClub && isClubAdmin) {
      api.clubs.listJoinRequests(activeClub.id)
        .then((reqs) => {
          const pending = (reqs || []).filter((r) => r.status === 'pending');
          setPendingCount(pending.length);
        })
        .catch(() => setPendingCount(0));
    } else {
      setPendingCount(0);
    }
  }, [activeClub?.id, isClubAdmin, location.pathname]);

  // Nav is only useful once the user holds a role in the active club; pending
  // applicants only see onboarding.
  const hasClubAccess = Boolean(user?.is_platform_admin || activeClub?.my_role);

  const navLinks = [
    { to: '/home', label: 'Home' },
    { to: '/documents', label: 'My Documents' },
    { to: '/templates', label: 'Templates' },
    { to: '/settings/club', label: 'Club Settings' },
  ];

  return (
    <header className="bg-white border-b border-slate-200 text-slate-800 shadow-sm sticky top-0 z-50">
      {/* Top Banner / SVNIT Permanent Branding */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Permanent SVNIT Logo and Institution Title */}
          <Link to="/home" className="flex items-center space-x-3 group">
            <div className="h-11 w-11 rounded-lg bg-white p-0.5 flex items-center justify-center border border-slate-200 shadow-sm overflow-hidden flex-shrink-0 group-hover:border-slate-300 transition-colors">
              <img
                src="/assets/svnit_crest.png"
                alt="SVNIT Crest"
                className="h-full w-full object-contain"
                onError={(e) => {
                  (e.target as HTMLElement).style.display = 'none';
                }}
              />
            </div>
            <div>
              <div className="font-bold text-sm sm:text-base tracking-wide flex items-center gap-2">
                <span className="text-[#1b365d] font-extrabold">SVNIT</span>
                <span className="text-slate-800 font-semibold">ClubDocs Portal</span>
              </div>
              <p className="text-xs text-slate-500 hidden sm:block">
                Sardar Vallabhbhai National Institute of Technology, Surat
              </p>
            </div>
          </Link>

          {/* Right Header Controls: Club Switcher, User Info, Logout */}
          <div className="flex items-center space-x-3 sm:space-x-4">
            {/* Club Switcher */}
            <div className="relative">
              {clubs.length > 0 ? (
                <button
                  type="button"
                  onClick={() => setDropdownOpen(!dropdownOpen)}
                  className="flex items-center space-x-2 bg-slate-50 hover:bg-slate-100 border border-slate-300 px-3 py-1.5 rounded-lg text-xs sm:text-sm font-medium text-slate-800 transition-colors shadow-sm"
                >
                  <Building2 className="w-4 h-4 text-[#1b365d]" />
                  <span className="max-w-[120px] sm:max-w-[180px] truncate">
                    {activeClub ? activeClub.name : 'Select Club'}
                  </span>
                  <ChevronDown className="w-3.5 h-3.5 text-slate-500" />
                </button>
              ) : (
                <button
                  type="button"
                  onClick={onOpenClubModal}
                  className="flex items-center space-x-1.5 bg-blue-50 hover:bg-blue-100 text-[#1b365d] border border-blue-200 px-3 py-1.5 rounded-lg text-xs sm:text-sm font-bold transition-colors"
                >
                  <Building2 className="w-4 h-4" />
                  <span>Choose Club</span>
                </button>
              )}

              {dropdownOpen && (
                <div
                  className="absolute right-0 mt-2 w-72 bg-white border border-slate-200 rounded-xl shadow-xl py-1 z-50 overflow-hidden"
                  onMouseLeave={() => setDropdownOpen(false)}
                >
                  <div className="px-3.5 py-2 text-xs font-semibold text-slate-400 uppercase tracking-wider border-b border-slate-100">
                    Switch Active Club
                  </div>
                  <div className="max-h-60 overflow-y-auto py-1">
                    {clubs.map((c) => (
                      <button
                        key={c.id}
                        type="button"
                        onClick={() => {
                          setActiveClubId(c.id);
                          setDropdownOpen(false);
                        }}
                        className={`w-full text-left px-3.5 py-2 text-xs sm:text-sm flex items-center justify-between hover:bg-slate-50 transition-colors ${
                          activeClub?.id === c.id ? 'text-[#1b365d] font-bold bg-blue-50/70' : 'text-slate-700'
                        }`}
                      >
                        <span className="truncate pr-2">{c.name}</span>
                        {c.my_role || user?.is_platform_admin ? (
                          <span className="text-[11px] text-slate-500 font-mono bg-slate-100 px-1.5 py-0.5 rounded border border-slate-200 flex-shrink-0">
                            {c.code || c.short_name}
                          </span>
                        ) : (
                          <span className="badge bg-amber-50 text-amber-700 border-amber-200 flex-shrink-0">Pending</span>
                        )}
                      </button>
                    ))}
                  </div>

                  <div className="border-t border-slate-100 p-1.5 bg-slate-50/60">
                    <Link
                      to="/onboarding/club"
                      onClick={() => setDropdownOpen(false)}
                      className="w-full text-left px-3 py-2 text-xs font-semibold text-[#1b365d] hover:bg-blue-50 rounded-lg flex items-center gap-2 transition-colors"
                    >
                      <span>+ Join or Add Another Club</span>
                    </Link>
                  </div>
                </div>
              )}
            </div>

            {/* User Profile Info */}
            <div className="hidden md:flex items-center space-x-2 border-l border-slate-200 pl-4">
              <UserCircle className="w-5 h-5 text-slate-500" />
              <div className="text-xs text-right">
                <p className="font-semibold text-slate-800">{user?.full_name}</p>
                <p className="text-slate-500 text-[10px] truncate max-w-[140px]">{user?.email}</p>
              </div>
              {user?.is_platform_admin ? (
                <span className="bg-amber-100 text-amber-800 text-[10px] px-2 py-0.5 rounded border border-amber-300 font-semibold">
                  Platform admin
                </span>
              ) : activeClub?.my_role ? (
                <span className="badge bg-blue-50 text-[#1b365d] border-blue-200 capitalize" title="Your access in this club">
                  {activeClub.my_role}
                </span>
              ) : null}
            </div>

            {/* Logout Button */}
            <button
              type="button"
              onClick={logout}
              title="Sign Out"
              className="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors border border-transparent hover:border-red-200"
            >
              <LogOut className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Navigation Tabs */}
        {hasClubAccess && (
        <div className="flex items-center justify-between border-t border-slate-100 pt-1 overflow-x-auto no-scrollbar">
          <div className="flex space-x-1">
            {navLinks.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                className={({ isActive }) =>
                  `px-3.5 py-2 text-xs sm:text-sm font-medium rounded-t-md transition-colors whitespace-nowrap flex-shrink-0 ${
                    isActive
                      ? 'bg-slate-50 text-[#1b365d] border-b-2 border-[#1b365d] font-bold'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50/60'
                  }`
                }
              >
                {link.label}
              </NavLink>
            ))}

            {isClubAdmin && (
              <NavLink
                to="/join-requests"
                className={({ isActive }) =>
                  `px-3 py-2 text-xs sm:text-sm font-medium rounded-t-md transition-colors whitespace-nowrap flex-shrink-0 flex items-center gap-1.5 ${
                    isActive
                      ? 'bg-slate-50 text-[#1b365d] border-b-2 border-[#1b365d] font-bold'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50/60'
                  }`
                }
              >
                <UserPlus className="w-3.5 h-3.5" />
                <span>Join Requests</span>
                {pendingCount > 0 && (
                  <span className="ml-1 px-1.5 py-0.2 bg-amber-500 text-white rounded-full text-[10px] font-bold">
                    {pendingCount}
                  </span>
                )}
              </NavLink>
            )}
          </div>
        </div>
        )}
      </div>
    </header>
  );
};
