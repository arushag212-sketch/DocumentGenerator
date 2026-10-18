import React from 'react';
import { useAuth } from '../context/AuthContext';
import { LogOut, ChevronDown, Building2, UserCircle } from 'lucide-react';

interface HeaderProps {
  currentTab: string;
  setCurrentTab: (tab: string) => void;
  memberCount: number;
  onOpenClubModal?: () => void;
}

export const Header: React.FC<HeaderProps> = ({ currentTab, setCurrentTab, memberCount: _memberCount, onOpenClubModal }) => {
  const { user, clubs, activeClub, setActiveClubId, logout } = useAuth();
  const [dropdownOpen, setDropdownOpen] = React.useState(false);

  return (
    <header className="bg-white border-b border-slate-200 text-slate-800 shadow-sm sticky top-0 z-50">
      {/* Top Banner / SVNIT Permanent Branding */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Permanent SVNIT Logo and Institution Title */}
          <div className="flex items-center space-x-3">
            <div className="h-11 w-11 rounded-lg bg-white p-0.5 flex items-center justify-center border border-slate-200 shadow-sm overflow-hidden flex-shrink-0">
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
          </div>

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
                        <span className="text-[11px] text-slate-500 font-mono bg-slate-100 px-1.5 py-0.5 rounded border border-slate-200 flex-shrink-0">
                          {c.code || c.short_name}
                        </span>
                      </button>
                    ))}
                  </div>

                  <div className="border-t border-slate-100 p-1.5 bg-slate-50/60">
                    <button
                      type="button"
                      onClick={() => {
                        setDropdownOpen(false);
                        onOpenClubModal?.();
                      }}
                      className="w-full text-left px-3 py-2 text-xs font-semibold text-[#1b365d] hover:bg-blue-50 rounded-lg flex items-center gap-2 transition-colors"
                    >
                      <span>+ Join or Add Another Club</span>
                    </button>
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
              {user?.is_platform_admin && (
                <span className="bg-amber-100 text-amber-800 text-[10px] px-2 py-0.5 rounded border border-amber-300 font-semibold">
                  Admin
                </span>
              )}
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
        <div className="flex items-center justify-between border-t border-slate-100 pt-1 overflow-x-auto no-scrollbar">
          <div className="flex space-x-1">
            {[
              { id: 'home', label: 'Home' },
              { id: 'documents', label: 'My Documents' },
              { id: 'templates', label: 'Templates' },
              { id: 'admin', label: 'Club settings' },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setCurrentTab(tab.id)}
                className={`px-3 py-2 text-xs sm:text-sm font-medium rounded-t-md transition-colors whitespace-nowrap flex-shrink-0 ${
                  currentTab === tab.id
                    ? 'bg-slate-50 text-[#1b365d] border-b-2 border-[#1b365d] font-bold'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50/60'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Secondary tools / legacy views */}
          <div className="hidden lg:flex items-center space-x-1 pl-4 text-xs text-slate-400">
            <button
              onClick={() => setCurrentTab('dashboard')}
              className={`px-2 py-1 rounded text-[11px] transition-colors ${
                currentTab === 'dashboard'
                  ? 'text-[#1b365d] font-semibold bg-blue-50'
                  : 'hover:text-slate-700'
              }`}
            >
              Dashboard
            </button>
            <button
              onClick={() => setCurrentTab('events')}
              className={`px-2 py-1 rounded text-[11px] transition-colors ${
                currentTab === 'events'
                  ? 'text-[#1b365d] font-semibold bg-blue-50'
                  : 'hover:text-slate-700'
              }`}
            >
              Events
            </button>
          </div>
        </div>
      </div>
    </header>
  );
};
