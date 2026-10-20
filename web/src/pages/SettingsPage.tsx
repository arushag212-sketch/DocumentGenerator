import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import { ClubMember, ClubPermissions } from '../types';
import { AdminTab } from '../components/settings/AdminTab';
import { MembersTab } from '../components/settings/MembersTab';
import { PeopleTab } from '../components/settings/PeopleTab';
import { AuditTab } from '../components/settings/AuditTab';
import { Settings, Users, UserCheck, ShieldAlert } from 'lucide-react';

export const SettingsPage: React.FC = () => {
  const { section } = useParams<{ section?: string }>();
  const { activeClub, refreshClubs } = useAuth();

  const [members, setMembers] = useState<ClubMember[]>([]);
  const [permissions, setPermissions] = useState<ClubPermissions | null>(null);
  const [loading, setLoading] = useState(true);

  const activeSection = section || 'club';

  const fetchData = async () => {
    if (!activeClub) return;
    try {
      const [membersData, permsData] = await Promise.all([
        api.clubs.getMembers(activeClub.id).catch(() => []),
        api.clubs.getPermissions(activeClub.id).catch(() => null),
      ]);
      setMembers(membersData);
      setPermissions(permsData);
    } catch {
      // Ignore
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [activeClub?.id]);

  if (!activeClub) {
    return (
      <div className="max-w-md mx-auto my-16 bg-white border border-slate-200 rounded-xl p-8 text-center shadow-sm">
        <p className="text-sm text-slate-600">Please select a club to view its settings.</p>
      </div>
    );
  }

  const tabs = [
    { id: 'club', label: 'Club Settings', icon: Settings },
    { id: 'members', label: 'Members', icon: Users },
    { id: 'people', label: 'People & Signatories', icon: UserCheck },
    { id: 'audit', label: 'Audit Trail', icon: ShieldAlert },
  ];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-8 py-8">
      {/* Sub-navigation bar */}
      <div className="flex border-b border-slate-200 mb-6 overflow-x-auto no-scrollbar">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeSection === tab.id;
          return (
            <Link
              key={tab.id}
              to={`/settings/${tab.id}`}
              className={`flex items-center gap-2 px-4 py-3 text-xs sm:text-sm font-semibold border-b-2 whitespace-nowrap transition-colors ${
                isActive
                  ? 'border-brand-700 text-brand-700'
                  : 'border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300'
              }`}
            >
              <Icon className="w-4 h-4" />
              <span>{tab.label}</span>
            </Link>
          );
        })}
      </div>

      {loading ? (
        <div className="text-center py-12 text-slate-400 text-xs">Loading settings...</div>
      ) : (
        <>
          {activeSection === 'club' && (
            <AdminTab
              clubId={activeClub.id}
              permissions={permissions}
              members={members}
              onRefreshMembers={() => {
                fetchData();
                refreshClubs();
              }}
            />
          )}

          {activeSection === 'members' && (
            <MembersTab
              clubId={activeClub.id}
              members={members}
              permissions={permissions}
              onRefresh={fetchData}
            />
          )}

          {activeSection === 'people' && (
            <PeopleTab clubId={activeClub.id} permissions={permissions} />
          )}

          {activeSection === 'audit' && (
            <AuditTab clubId={activeClub.id} />
          )}
        </>
      )}
    </div>
  );
};
