import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ClubMember, ClubPermissions, RoleName, Invite } from '../types';
import { api } from '../api/client';
import {
  Users,
  UserPlus,
  Trash2,
  Shield,
  Info,
  CheckCircle2,
  Link as LinkIcon,
  Copy,
  Ban,
  Clock,
  Sparkles,
  AlertCircle,
  UserCheck,
} from 'lucide-react';

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

  // Invites state
  const [invites, setInvites] = useState<Invite[]>([]);
  const [inviteRole, setInviteRole] = useState('editor');
  const [inviteMaxUses, setInviteMaxUses] = useState(1);
  const [inviteExpiryDays, setInviteExpiryDays] = useState(7);
  const [creatingInvite, setCreatingInvite] = useState(false);
  const [copiedCode, setCopiedCode] = useState<string | null>(null);

  const canEdit = permissions?.can_edit_members || permissions?.is_platform_admin || permissions?.role === 'admin' || permissions?.role === 'owner';
  const myRole = permissions?.role || 'viewer';

  const fetchInvites = async () => {
    if (!canEdit) return;
    try {
      const data = await api.clubs.getInvites(clubId);
      setInvites(data);
    } catch {
      // Ignored if user lacks permission
    }
  };

  useEffect(() => {
    fetchInvites();
  }, [clubId, canEdit]);

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

  const handleCreateInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setCreatingInvite(true);

    try {
      const newInv = await api.clubs.createInvite(clubId, {
        role: inviteRole,
        max_uses: Number(inviteMaxUses),
        expiry_days: Number(inviteExpiryDays),
      });
      setSuccess(`Invite code created: ${newInv.code} (${newInv.role}, ${newInv.max_uses} use(s))`);
      await fetchInvites();
    } catch (err: any) {
      setError(err.message || 'Failed to create invite');
    } finally {
      setCreatingInvite(false);
    }
  };

  const handleRevokeInvite = async (inviteId: string) => {
    if (!confirm('Revoke this invite? Anyone with the link will no longer be able to use it.')) return;
    setError(null);
    try {
      await api.clubs.revokeInvite(clubId, inviteId);
      setSuccess('Invite revoked successfully.');
      await fetchInvites();
    } catch (err: any) {
      setError(err.message || 'Failed to revoke invite');
    }
  };

  const handleCopyLink = (code: string) => {
    const link = `${window.location.origin}/?invite=${code}`;
    navigator.clipboard.writeText(link);
    setCopiedCode(code);
    setTimeout(() => setCopiedCode(null), 2500);
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
    owner: 'bg-rose-100 text-rose-800 border-rose-300 font-bold',
    admin: 'bg-purple-100 text-purple-800 border-purple-200 font-bold',
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
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4 sm:p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <Users className="w-6 h-6 text-slate-700" />
            <h2 className="text-lg sm:text-xl font-bold text-slate-900">Club Members & Access Control</h2>
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
            <span>You have permissions to manage team members & invites</span>
          </div>
        )}
      </div>

      {/* Feedback Alerts */}
      {error && (
        <div className="p-3 sm:p-4 bg-red-50 border border-red-200 rounded-xl text-xs sm:text-sm text-red-800 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 flex-shrink-0 text-red-600" />
          <span>{error}</span>
        </div>
      )}

      {success && (
        <div className="p-3 sm:p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-xs sm:text-sm text-emerald-800 flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 flex-shrink-0 text-emerald-600" />
          <span>{success}</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Members List */}
        <div className="lg:col-span-2 space-y-6">
          {/* PENDING JOIN REQUESTS (HEAD APPROVAL FLOW) */}
          {canEdit && (
            <div className="flex items-center justify-between p-4 bg-amber-50/60 border border-amber-200 rounded-2xl">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-amber-100 text-amber-700 flex items-center justify-center font-bold">
                  <UserCheck className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="text-xs sm:text-sm font-bold text-slate-900">Pending Join Requests</h4>
                  <p className="text-xs text-slate-500">Review applicants and approve club roles</p>
                </div>
              </div>
              <Link
                to="/join-requests"
                className="px-3.5 py-2 bg-[#1b365d] hover:bg-[#132742] text-white text-xs font-bold rounded-xl transition-colors shadow-sm"
              >
                Review Requests →
              </Link>
            </div>
          )}

          <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
            <div className="px-4 sm:px-6 py-4 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
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
                  <li key={m.id} className="p-4 sm:px-6 hover:bg-slate-50 transition-colors flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-semibold text-sm text-slate-900 truncate">
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
                      <p className="text-xs text-slate-500 mt-0.5 truncate">{m.user?.email}</p>
                      {m.title && (
                        <p className="text-[11px] text-slate-400 mt-0.5 italic">{m.title}</p>
                      )}
                    </div>

                    {canEdit && (
                      <button
                        type="button"
                        onClick={() => handleRemoveMember(m.id, m.user?.full_name || m.user?.email || 'Member')}
                        className="text-slate-400 hover:text-red-600 p-1.5 rounded-lg hover:bg-red-50 transition-colors flex-shrink-0"
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

          {/* INVITES SECTION */}
          {canEdit && (
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
              <div className="px-4 sm:px-6 py-4 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <LinkIcon className="w-4 h-4 text-[#1b365d]" />
                  <span className="text-xs font-semibold text-slate-600 uppercase tracking-wider">
                    Club Invites & Shareable Links ({invites.length})
                  </span>
                </div>
              </div>

              {invites.length === 0 ? (
                <div className="p-6 text-center text-xs text-slate-500">
                  No invites active. Create an invite link below to invite members.
                </div>
              ) : (
                <div className="divide-y divide-slate-100">
                  {invites.map((inv) => {
                    const isExpired = inv.expires_at && new Date(inv.expires_at) < new Date();
                    const isUsedUp = inv.max_uses > 0 && inv.use_count >= inv.max_uses;
                    const isActive = !inv.revoked && !isExpired && !isUsedUp;

                    return (
                      <div key={inv.id} className="p-4 sm:px-6 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
                        <div>
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-mono font-bold text-sm text-[#1b365d] bg-blue-50 px-2 py-0.5 rounded border border-blue-200">
                              {inv.code}
                            </span>
                            <span
                              className={`text-[10px] font-semibold uppercase px-2 py-0.5 rounded border ${
                                roleColors[inv.role] || 'bg-slate-100'
                              }`}
                            >
                              {inv.role}
                            </span>

                            {inv.revoked ? (
                              <span className="bg-red-100 text-red-800 text-[10px] font-bold px-2 py-0.5 rounded border border-red-300">
                                Revoked
                              </span>
                            ) : isUsedUp ? (
                              <span className="bg-slate-100 text-slate-600 text-[10px] font-bold px-2 py-0.5 rounded border border-slate-300">
                                Used Up
                              </span>
                            ) : isExpired ? (
                              <span className="bg-amber-100 text-amber-800 text-[10px] font-bold px-2 py-0.5 rounded border border-amber-300">
                                Expired
                              </span>
                            ) : (
                              <span className="bg-emerald-100 text-emerald-800 text-[10px] font-bold px-2 py-0.5 rounded border border-emerald-300">
                                Active
                              </span>
                            )}
                          </div>

                          <div className="text-slate-500 text-[11px] mt-1.5 flex items-center gap-3">
                            <span>
                              Uses: <strong>{inv.use_count} / {inv.max_uses}</strong>
                            </span>
                            {inv.expires_at && (
                              <span className="flex items-center gap-1">
                                <Clock className="w-3 h-3 text-slate-400" />
                                Expires: {new Date(inv.expires_at).toLocaleDateString()}
                              </span>
                            )}
                          </div>
                        </div>

                        <div className="flex items-center gap-2 self-end sm:self-center">
                          {isActive && (
                            <button
                              type="button"
                              onClick={() => handleCopyLink(inv.code)}
                              className="inline-flex items-center gap-1 bg-slate-100 hover:bg-slate-200 text-slate-800 px-2.5 py-1.5 rounded-lg font-semibold transition-colors"
                            >
                              <Copy className="w-3.5 h-3.5" />
                              <span>{copiedCode === inv.code ? 'Copied Link!' : 'Copy Link'}</span>
                            </button>
                          )}

                          {isActive && (
                            <button
                              type="button"
                              onClick={() => handleRevokeInvite(inv.id)}
                              className="inline-flex items-center gap-1 text-red-600 hover:bg-red-50 px-2.5 py-1.5 rounded-lg font-semibold transition-colors"
                              title="Revoke Invite"
                            >
                              <Ban className="w-3.5 h-3.5" />
                              <span>Revoke</span>
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Right Column: Forms */}
        <div className="space-y-6">
          {/* Create Invite Link Card */}
          {canEdit && (
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5 space-y-4">
              <div className="flex items-center gap-2 pb-3 border-b border-slate-100">
                <Sparkles className="w-5 h-5 text-[#1b365d]" />
                <h3 className="font-semibold text-sm text-slate-900">Create Club Invite</h3>
              </div>

              <p className="text-xs text-slate-500">
                Create a join link with a specified role and 7-day expiry. New users can register and existing users can join directly.
              </p>

              <form onSubmit={handleCreateInvite} className="space-y-3 text-xs">
                <div>
                  <label className="block font-medium text-slate-700 mb-1">Assigned Role</label>
                  <select
                    value={inviteRole}
                    onChange={(e) => setInviteRole(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#1b365d]"
                  >
                    {myRole === 'owner' && <option value="admin">Admin</option>}
                    {myRole === 'admin' && <option value="admin">Admin</option>}
                    <option value="editor">Editor</option>
                    <option value="viewer">Viewer</option>
                  </select>
                  <p className="text-[10px] text-slate-400 mt-1">
                    Roles cannot exceed your own permissions ({myRole}).
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block font-medium text-slate-700 mb-1">Max Uses</label>
                    <input
                      type="number"
                      min={1}
                      max={100}
                      required
                      value={inviteMaxUses}
                      onChange={(e) => setInviteMaxUses(Number(e.target.value))}
                      className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#1b365d]"
                    />
                  </div>
                  <div>
                    <label className="block font-medium text-slate-700 mb-1">Expiry (Days)</label>
                    <input
                      type="number"
                      min={1}
                      max={30}
                      required
                      value={inviteExpiryDays}
                      onChange={(e) => setInviteExpiryDays(Number(e.target.value))}
                      className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#1b365d]"
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={creatingInvite}
                  className="w-full mt-2 bg-[#1b365d] hover:bg-[#162a4a] text-white font-semibold text-xs py-2.5 px-4 rounded-lg transition-colors shadow-sm disabled:opacity-50"
                >
                  {creatingInvite ? 'Generating Invite...' : 'Generate Invite Link'}
                </button>
              </form>
            </div>
          )}

          {/* Add Direct Member Form */}
          {canEdit && (
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5 space-y-4">
              <div className="flex items-center gap-2 pb-3 border-b border-slate-100">
                <UserPlus className="w-5 h-5 text-amber-600" />
                <h3 className="font-semibold text-sm text-slate-900">Direct Member Add</h3>
              </div>

              <form onSubmit={handleAddMember} className="space-y-3 text-xs">
                <div>
                  <label className="block font-medium text-slate-700 mb-1">
                    User Email (must be registered)
                  </label>
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="student@example.com"
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500"
                  />
                </div>

                <div>
                  <label className="block font-medium text-slate-700 mb-1">
                    Club Role
                  </label>
                  <select
                    value={role}
                    onChange={(e) => setRole(e.target.value as RoleName)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500"
                  >
                    <option value="editor">Editor (Draft Documents)</option>
                    <option value="viewer">Viewer (Read Only)</option>
                    <option value="treasurer">Treasurer (Financial Docs)</option>
                    <option value="lead">Lead (Full Club Control)</option>
                  </select>
                </div>

                <div>
                  <label className="block font-medium text-slate-700 mb-1">
                    Designation / Title (Optional)
                  </label>
                  <input
                    type="text"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder="e.g. Secretary, Event Head"
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500"
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
              <li>• <strong>Admin / Lead</strong>: Full access to documents, members, venues, numbering, and letterheads.</li>
              <li>• <strong>Treasurer</strong>: Manage expenses, bill summaries, and vouchers.</li>
              <li>• <strong>Editor</strong>: Draft documents, view venues & numbering (read-only).</li>
              <li>• <strong>Viewer</strong>: Read-only access to finalized documents.</li>
            </ul>
          </div>
        </div>
      </div>

    </div>
  );
};


