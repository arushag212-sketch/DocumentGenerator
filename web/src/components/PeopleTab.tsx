import React, { useState, useEffect } from 'react';
import { Person, ClubPermissions } from '../types';
import { api } from '../api/client';
import { UserCheck, Lock, Eye, EyeOff, Plus } from 'lucide-react';

interface PeopleTabProps {
  clubId: string | number;
  permissions: ClubPermissions | null;
}

export const PeopleTab: React.FC<PeopleTabProps> = ({ clubId, permissions }) => {
  const [people, setPeople] = useState<Person[]>([]);
  const [revealedMobiles, setRevealedMobiles] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);

  // Form state
  const [name, setName] = useState('');
  const [rollNumber, setRollNumber] = useState('');
  const [branch, setBranch] = useState('');
  const [designation, setDesignation] = useState('');
  const [mobile, setMobile] = useState('');
  const [role, setRole] = useState('faculty_advisor');

  const canViewSensitive = permissions?.can_view_sensitive || permissions?.is_platform_admin;

  const fetchPeople = async () => {
    try {
      setLoading(true);
      const data = await api.clubs.getPeople(clubId);
      setPeople(data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPeople();
    setRevealedMobiles({});
  }, [clubId]);

  const handleReveal = async (personId: string | number) => {
    const key = String(personId);
    if (revealedMobiles[key]) {
      // Toggle off
      const next = { ...revealedMobiles };
      delete next[key];
      setRevealedMobiles(next);
      return;
    }

    try {
      const res = await api.clubs.revealSensitive(clubId, personId);
      if (res.value) {
        setRevealedMobiles((prev) => ({ ...prev, [String(personId)]: res.value || '' }));
      }
    } catch (err: any) {
      alert(`Permission Denied: ${err.message}`);
    }
  };

  const handleAddPerson = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.clubs.addPerson(clubId, {
        name,
        roll_number: rollNumber || undefined,
        branch: branch || undefined,
        designation: designation || undefined,
        mobile: mobile || undefined,
        role,
      });
      setShowAddModal(false);
      setName('');
      setRollNumber('');
      setBranch('');
      setDesignation('');
      setMobile('');
      fetchPeople();
    } catch (err: any) {
      alert(`Error adding person: ${err.message}`);
    }
  };

  return (
    <div className="space-y-6">
      {/* Banner explaining security / encryption */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <UserCheck className="w-6 h-6 text-slate-700" />
              <h2 className="text-xl font-bold text-slate-900">Faculty, Staff & Official Signatories</h2>
            </div>
            <p className="mt-1 text-xs text-slate-500">
              Field-level Fernet AES-128 encryption protects personal contact numbers at rest. Numbers are masked by default.
            </p>
          </div>

          <div className="flex items-center gap-3">
            {permissions?.can_edit_settings && (
              <button
                type="button"
                onClick={() => setShowAddModal(true)}
                className="inline-flex items-center gap-1.5 bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold px-3 py-2 rounded-lg transition-colors"
              >
                <Plus className="w-4 h-4" />
                Add Official
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Directory Table */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
          <span className="text-xs font-semibold text-slate-600 uppercase tracking-wider">
            Official Directory ({people.length})
          </span>
          <div className="flex items-center gap-1.5 text-xs text-emerald-700 font-medium">
            <Lock className="w-3.5 h-3.5" />
            <span>Fernet-256 Encrypted Storage</span>
          </div>
        </div>

        {loading ? (
          <div className="p-8 text-center text-slate-400 text-sm">Loading directory...</div>
        ) : people.length === 0 ? (
          <div className="p-8 text-center text-slate-500 text-sm">No officials registered for this club.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-100/60 text-slate-600 uppercase text-[10px] tracking-wider border-b border-slate-200">
                <tr>
                  <th className="py-3 px-6">Name</th>
                  <th className="py-3 px-6">Designation / Role</th>
                  <th className="py-3 px-6">Branch / Dept</th>
                  <th className="py-3 px-6">Roll / ID</th>
                  <th className="py-3 px-6">Contact Mobile (Encrypted)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {people.map((p) => {
                  const pidKey = String(p.id);
                  const isRevealed = Boolean(revealedMobiles[pidKey]);
                  const displayedMobile = isRevealed
                    ? revealedMobiles[pidKey]
                    : p.mobile || '—';

                  return (
                    <tr key={p.id} className="hover:bg-slate-50/80 transition-colors">
                      <td className="py-3.5 px-6 font-semibold text-slate-900">{p.name}</td>
                      <td className="py-3.5 px-6 text-slate-600">
                        {p.designation || p.role || '—'}
                      </td>
                      <td className="py-3.5 px-6 text-slate-600">{p.branch || '—'}</td>
                      <td className="py-3.5 px-6 font-mono text-slate-500">{p.roll_number || '—'}</td>
                      <td className="py-3.5 px-6">
                        <div className="flex items-center gap-2">
                          <span
                            className={`font-mono text-xs px-2 py-0.5 rounded border ${
                              isRevealed
                                ? 'bg-amber-50 text-amber-900 border-amber-300 font-bold'
                                : 'bg-slate-100 text-slate-600 border-slate-200'
                            }`}
                          >
                            {displayedMobile}
                          </span>
                          {p.mobile && canViewSensitive && (
                            <button
                              type="button"
                              onClick={() => handleReveal(p.id)}
                              className="text-slate-400 hover:text-slate-700 p-1 rounded hover:bg-slate-100 transition-colors"
                              title={isRevealed ? 'Hide number' : 'Decrypt & reveal number'}
                            >
                              {isRevealed ? (
                                <EyeOff className="w-3.5 h-3.5 text-amber-600" />
                              ) : (
                                <Eye className="w-3.5 h-3.5" />
                              )}
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Add Person Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6 space-y-4">
            <h3 className="font-bold text-base text-slate-900">Add Club Official / Signatory</h3>
            <form onSubmit={handleAddPerson} className="space-y-3 text-xs">
              <div>
                <label className="block font-medium text-slate-700 mb-1">Full Name</label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Demo Faculty Chairman"
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-amber-500"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium text-slate-700 mb-1">Designation</label>
                  <input
                    type="text"
                    value={designation}
                    onChange={(e) => setDesignation(e.target.value)}
                    placeholder="e.g. Chairman CSE"
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-amber-500"
                  />
                </div>
                <div>
                  <label className="block font-medium text-slate-700 mb-1">Branch / Dept</label>
                  <input
                    type="text"
                    value={branch}
                    onChange={(e) => setBranch(e.target.value)}
                    placeholder="e.g. CSE / DoCSE"
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-amber-500"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium text-slate-700 mb-1">Roll / Employee ID</label>
                  <input
                    type="text"
                    value={rollNumber}
                    onChange={(e) => setRollNumber(e.target.value)}
                    placeholder="e.g. DEMO-001"
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-amber-500"
                  />
                </div>
                <div>
                  <label className="block font-medium text-slate-700 mb-1">Mobile (Encrypted)</label>
                  <input
                    type="tel"
                    value={mobile}
                    onChange={(e) => setMobile(e.target.value)}
                    placeholder="e.g. 9876543210"
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-amber-500"
                  />
                </div>
              </div>
              <div>
                <label className="block font-medium text-slate-700 mb-1">Role Classification</label>
                <select
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-amber-500"
                >
                  <option value="faculty_advisor">Faculty Advisor</option>
                  <option value="co_chairman">Co-Chairman</option>
                  <option value="technical_assistant">Technical Assistant</option>
                  <option value="student_head">Student Head</option>
                  <option value="approver">Approval Authority</option>
                </select>
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 border border-slate-300 rounded-lg text-slate-700 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-amber-500 hover:bg-amber-600 text-white rounded-lg font-semibold"
                >
                  Save & Encrypt
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
