import React, { useState } from 'react';
import { ClubMember, ClubPermissions, RoleName } from '../types';
import { api } from '../api/client';
import { Users, UserPlus, Trash2, Shield, Info, CheckCircle2 } from 'lucide-react';

interface MembersTabProps {
  clubId: string | number;
  members: ClubMember[];
  permissions: ClubPermissions | null;
  onRefresh: () => void;
}

export const MembersTab: React.FC<MembersTabProps> = ({
  clubId,
  members,
  permissions,
  onRefresh,
}) => {
  const [email, setEmail] = useState('');
  const [role, setRole] = useState<RoleName>('editor');
  const [title, setTitle] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const canEdit = permissions?.can_edit_members || permissions?.is_platform_admin;

  const handleAddMember = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setLoading(true);

    try {
      await api.clubs.addMember(clubId, {
        user_email: email.trim(),
        role,
        title: title.trim() || undefined,
      });
      setEmail('');
      setTitle('');
      setSuccess(`Added ${email} as ${role}`);
      onRefresh();
    } catch (err: any) {
      setError(err.message || 'Failed to add member');
    } finally {
      setLoading(false);
    }
  };

  const handleRemoveMember = async (memberId: string | number, memberName: string) => {
    if (!confirm(`Are you sure you want to remove ${memberName}?`)) return;
    try {
      await api.clubs.removeMember(clubId, memberId);
      onRefresh();
    } catch (err: any) {
      alert(`Error removing member: ${err.message}`);
    }
  };

  const roleColors: Record<string, string> = {
    lead: 'bg-purple-100 text-purple-800 border-purple-200',
    co_lead: 'bg-indigo-100 text-indigo-800 border-indigo-200',
    treasurer: 'bg-emerald-100 text-emerald-800 border-emerald-200',
    faculty_advisor: 'bg-blue-100 text-blue-800 border-blue-200',
    editor: 'bg-amber-100 text-amber-800 border-amber-200',
    viewer: 'bg-slate-100 text-slate-800 border-slate-200',
  };

  return (
    <div className="space-y-6">
      {/* Header with accurate count */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <Users className="w-6 h-6 text-slate-700" />
            <h2 className="text-xl font-bold text-slate-900">Club Members & Team</h2>
            <span className="bg-slate-100 text-slate-700 font-mono text-xs font-bold px-2.5 py-0.5 rounded-full border border-slate-300">
              Total: {members.length}
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-500">
            Assigned roles determine document authoring, budget finalization, and security access.
          </p>
        </div>

        {canEdit && (
          <div className="text-xs text-slate-500 bg-slate-50 px-3 py-1.5 rounded-lg border border-slate-200 flex items-center gap-1.5">
            <Shield className="w-4 h-4 text-emerald-600" />
            <span>You have permissions to manage team members</span>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Members List */}
        <div className="lg:col-span-2 space-y-4">
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-600 uppercase tracking-wider">
                Member Directory ({members.length})
              </span>
            </div>

            {members.length === 0 ? (
              <div className="p-8 text-center text-slate-500 text-sm">
                No members found in this club.
              </div>
            ) : (
              <ul className="divide-y divide-slate-100">
                {members.map((m) => (
                  <li key={m.id} className="p-4 sm:px-6 hover:bg-slate-50 transition-colors flex items-center justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-sm text-slate-900">
                          {m.user?.full_name || 'Member'}
                        </span>
                        <span
                          className={`text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full border ${
                            roleColors[m.role] || 'bg-slate-100 text-slate-700'
                          }`}
                        >
                          {m.role.replace('_', ' ')}
                        </span>
                      </div>
                      <p className="text-xs text-slate-500 mt-0.5">{m.user?.email}</p>
                      {m.title && (
                        <p className="text-[11px] text-slate-400 mt-0.5 italic">{m.title}</p>
                      )}
                    </div>

                    {canEdit && (
                      <button
                        type="button"
                        onClick={() => handleRemoveMember(m.id, m.user?.full_name || m.user?.email || 'Member')}
                        className="text-slate-400 hover:text-red-600 p-1.5 rounded-lg hover:bg-red-50 transition-colors"
                        title="Remove member"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        {/* Add Member Form & Role Information */}
        <div className="space-y-4">
          {canEdit && (
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
              <div className="flex items-center gap-2 pb-3 border-b border-slate-100 mb-4">
                <UserPlus className="w-5 h-5 text-amber-600" />
                <h3 className="font-semibold text-sm text-slate-900">Add Club Member</h3>
              </div>

              {error && (
                <div className="mb-3 p-2.5 rounded bg-red-50 border border-red-200 text-red-700 text-xs">
                  {error}
                </div>
              )}
              {success && (
                <div className="mb-3 p-2.5 rounded bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs flex items-center gap-1.5">
                  <CheckCircle2 className="w-4 h-4" />
                  {success}
                </div>
              )}

              <form onSubmit={handleAddMember} className="space-y-3">
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">
                    User Email (must be registered)
                  </label>
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="student@example.com"
                    className="w-full text-xs px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">
                    Club Role
                  </label>
                  <select
                    value={role}
                    onChange={(e) => setRole(e.target.value as RoleName)}
                    className="w-full text-xs px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500"
                  >
                    <option value="lead">Lead (Full Club Control)</option>
                    <option value="co_lead">Co-Lead</option>
                    <option value="treasurer">Treasurer (Financial Docs)</option>
                    <option value="faculty_advisor">Faculty Advisor</option>
                    <option value="editor">Editor (Draft Documents)</option>
                    <option value="viewer">Viewer (Read Only)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">
                    Designation / Title (Optional)
                  </label>
                  <input
                    type="text"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder="e.g. Secretary, Event Head"
                    className="w-full text-xs px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500"
                  />
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full mt-2 bg-amber-500 hover:bg-amber-600 text-white font-medium text-xs py-2 px-4 rounded-lg transition-colors shadow-sm disabled:opacity-50"
                >
                  {loading ? 'Adding...' : 'Add to Club'}
                </button>
              </form>
            </div>
          )}

          {/* Role Permissions Matrix Card */}
          <div className="bg-slate-50 rounded-xl border border-slate-200 p-4 text-xs space-y-2">
            <div className="flex items-center gap-1.5 font-semibold text-slate-800">
              <Info className="w-4 h-4 text-slate-500" />
              Role Permissions Overview
            </div>
            <ul className="space-y-1.5 text-slate-600 text-[11px]">
              <li>• <strong>Lead</strong>: Full access to documents, members, and sensitive fields.</li>
              <li>• <strong>Treasurer</strong>: Manage expenses, bill summaries, and vouchers.</li>
              <li>• <strong>Editor</strong>: Draft documents and suggest counter numbers.</li>
              <li>• <strong>Viewer</strong>: Read-only access to finalized documents.</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};
