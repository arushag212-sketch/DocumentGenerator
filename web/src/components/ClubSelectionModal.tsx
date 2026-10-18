import React, { useState, useEffect } from 'react';
import { Search, Plus, Clock, CheckCircle2, Building2, Users, ShieldAlert, X } from 'lucide-react';
import { api } from '../api/client';
import { ClubSearchResult } from '../types';
import { useAuth } from '../context/AuthContext';

interface ClubSelectionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onClubSelected: (clubId: string) => void;
}

const FIXED_POSITIONS = [
  'Student Head/Chairperson',
  'Student Secretary',
  'Treasurer',
  'Core member',
  'Faculty Chairman',
  'Faculty Co-Chairman',
  'Member',
  'Other',
];

export const ClubSelectionModal: React.FC<ClubSelectionModalProps> = ({
  isOpen,
  onClose,
  onClubSelected,
}) => {
  const { refreshClubs, setActiveClubId } = useAuth();
  const [query, setQuery] = useState('');
  const [searchResults, setSearchResults] = useState<ClubSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Join request state
  const [selectedClubForJoin, setSelectedClubForJoin] = useState<ClubSearchResult | null>(null);
  const [position, setPosition] = useState('Member');
  const [otherNote, setOtherNote] = useState('');
  const [submittingJoin, setSubmittingJoin] = useState(false);

  // Create club state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newClubName, setNewClubName] = useState('');
  const [newClubShortName, setNewClubShortName] = useState('');
  const [newClubChapterCode, setNewClubChapterCode] = useState('');
  const [creatorPosition, setCreatorPosition] = useState('Student Head/Chairperson');
  const [creatorOtherNote, setCreatorOtherNote] = useState('');
  const [creatorIsSignatory, setCreatorIsSignatory] = useState(true);
  const [submittingCreate, setSubmittingCreate] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const fetchClubs = async (searchQuery: string) => {
    setLoading(true);
    setError(null);
    try {
      const results = await api.clubs.search(searchQuery);
      setSearchResults(results);
    } catch (err: any) {
      setError(err.message || 'Failed to search clubs');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchClubs(query);
    }
  }, [isOpen, query]);

  if (!isOpen) return null;

  const handleJoinSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedClubForJoin) return;

    let finalPos = position;
    if (position === 'Other') {
      const trimmed = otherNote.trim();
      if (!trimmed) {
        setError('Please enter your position title.');
        return;
      }
      if (!/^[A-Za-z\s\-&/]+$/.test(trimmed)) {
        setError('Custom position can only contain letters, spaces, hyphens, ampersands and slashes.');
        return;
      }
      if (trimmed.length > 60) {
        setError('Position cannot exceed 60 characters.');
        return;
      }
      finalPos = trimmed;
    }

    setSubmittingJoin(true);
    setError(null);
    try {
      await api.clubs.joinRequest(selectedClubForJoin.id, { position: finalPos });
      const targetClubId = selectedClubForJoin.id;
      setSelectedClubForJoin(null);
      setPosition('Member');
      setOtherNote('');
      await refreshClubs();
      setActiveClubId(targetClubId);
      onClubSelected(targetClubId);
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to submit join request');
    } finally {
      setSubmittingJoin(false);
    }
  };

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const nameTrimmed = newClubName.trim();
    const shortTrimmed = newClubShortName.trim();

    if (!nameTrimmed || nameTrimmed.length < 3) {
      setCreateError('Club name must be at least 3 characters.');
      return;
    }
    if (!shortTrimmed || shortTrimmed.length < 1) {
      setCreateError('Short name is required (e.g. ROBO, ACM).');
      return;
    }

    let finalCreatorPos = creatorPosition;
    if (creatorPosition === 'Other') {
      const trimmed = creatorOtherNote.trim();
      if (!trimmed || !/^[A-Za-z\s\-&/]+$/.test(trimmed) || trimmed.length > 60) {
        setCreateError('Custom position must be 1-60 characters and contain letters/symbols only.');
        return;
      }
      finalCreatorPos = trimmed;
    }

    setSubmittingCreate(true);
    setCreateError(null);
    try {
      const newClub = await api.clubs.createClub({
        name: nameTrimmed,
        short_name: shortTrimmed,
        chapter_code: newClubChapterCode.trim() || undefined,
        position: finalCreatorPos,
        is_signatory: creatorIsSignatory,
      });

      await refreshClubs();
      setActiveClubId(newClub.id);
      onClubSelected(String(newClub.id));
      setShowCreateModal(false);
      onClose();
    } catch (err: any) {
      setCreateError(err.message || 'Failed to create club');
    } finally {
      setSubmittingCreate(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full border border-slate-200 overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="p-5 border-b border-slate-100 flex items-center justify-between bg-slate-50/60">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-[#1b365d]/10 text-[#1b365d] rounded-xl">
              <Building2 className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base sm:text-lg font-bold text-slate-900">Which club are you in?</h2>
              <p className="text-xs text-slate-500">Search student chapters or add a new club</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Search & Actions Bar */}
        <div className="p-4 border-b border-slate-100 flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search by club name or abbreviation..."
              className="w-full pl-9 pr-3 py-2 text-sm bg-slate-50 border border-slate-200 rounded-xl focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#1b365d]/20 focus:border-[#1b365d]"
            />
          </div>
          <button
            onClick={() => setShowCreateModal(true)}
            className="px-3.5 py-2 text-xs sm:text-sm font-semibold text-[#1b365d] bg-blue-50/80 hover:bg-blue-100/80 border border-blue-200 rounded-xl flex items-center justify-center gap-1.5 transition-colors whitespace-nowrap"
          >
            <Plus className="w-4 h-4" />
            My club isn't listed
          </button>
        </div>

        {error && (
          <div className="mx-4 mt-3 p-3 text-xs bg-red-50 border border-red-200 rounded-xl text-red-700 flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Clubs List */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {loading ? (
            <div className="py-12 text-center text-xs text-slate-400">Loading clubs...</div>
          ) : searchResults.length === 0 ? (
            <div className="py-12 text-center">
              <Building2 className="w-10 h-10 text-slate-300 mx-auto mb-2" />
              <p className="text-sm font-medium text-slate-700">No clubs found</p>
              <p className="text-xs text-slate-500 mt-1">Try a different search term or add your club.</p>
            </div>
          ) : (
            searchResults.map((club) => {
              const isMember = Boolean(club.membership_role);
              const isPending = club.join_request_status === 'pending';

              return (
                <div
                  key={club.id}
                  className="p-4 rounded-xl border border-slate-200 hover:border-slate-300 hover:shadow-sm transition-all bg-white flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                >
                  <div className="flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="font-bold text-sm text-slate-900">{club.name}</h3>
                      {club.short_name && (
                        <span className="px-2 py-0.5 text-[11px] font-mono font-bold bg-slate-100 text-slate-700 rounded border border-slate-200">
                          {club.short_name}
                        </span>
                      )}
                    </div>
                    <div className="mt-1 flex items-center gap-3 text-xs text-slate-500">
                      <span className="flex items-center gap-1">
                        <Users className="w-3.5 h-3.5" />
                        {club.member_count} member{club.member_count === 1 ? '' : 's'}
                      </span>
                      {club.admin_name && (
                        <span>Admin: {club.admin_name}</span>
                      )}
                    </div>
                  </div>

                  {/* Actions / Status */}
                  <div className="flex items-center gap-2 self-end sm:self-center">
                    {isMember ? (
                      <button
                        onClick={() => {
                          setActiveClubId(club.id);
                          onClubSelected(club.id);
                          onClose();
                        }}
                        className="px-3.5 py-1.5 text-xs font-semibold text-emerald-800 bg-emerald-50 hover:bg-emerald-100 border border-emerald-300 rounded-lg flex items-center gap-1 transition-colors"
                      >
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        Enter Club
                      </button>
                    ) : isPending ? (
                      <button
                        onClick={() => {
                          setActiveClubId(club.id);
                          onClubSelected(club.id);
                          onClose();
                        }}
                        className="px-3 py-1.5 text-xs font-medium text-amber-800 bg-amber-50 hover:bg-amber-100 border border-amber-200 rounded-lg flex items-center gap-1.5 cursor-pointer transition-colors"
                        title="Click to view approval status"
                      >
                        <Clock className="w-3.5 h-3.5 text-amber-600 animate-pulse" />
                        <span>Waiting for approval from {club.admin_name || 'Admin'}</span>
                      </button>
                    ) : (
                      <button
                        onClick={() => {
                          setSelectedClubForJoin(club);
                          setPosition('Member');
                          setOtherNote('');
                          setError(null);
                        }}
                        className="px-3.5 py-1.5 text-xs font-semibold text-[#1b365d] bg-slate-100 hover:bg-[#1b365d] hover:text-white rounded-lg transition-colors border border-slate-200"
                      >
                        Join Club
                      </button>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-100 bg-slate-50/60 text-right">
          <button
            onClick={onClose}
            className="px-4 py-2 text-xs font-medium text-slate-600 hover:text-slate-800"
          >
            Close
          </button>
        </div>
      </div>

      {/* Position Selector Modal (Join Request) */}
      {selectedClubForJoin && (
        <div className="fixed inset-0 z-60 bg-slate-900/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full border border-slate-200 p-6">
            <h3 className="text-base font-bold text-slate-900">What's your position?</h3>
            <p className="text-xs text-slate-500 mt-1">
              Select your role in <strong>{selectedClubForJoin.name}</strong>.
            </p>

            <form onSubmit={handleJoinSubmit} className="mt-4 space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">
                  Position
                </label>
                <select
                  value={position}
                  onChange={(e) => setPosition(e.target.value)}
                  className="w-full text-xs sm:text-sm bg-white border border-slate-300 rounded-xl px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#1b365d]/20 focus:border-[#1b365d]"
                >
                  {FIXED_POSITIONS.map((pos) => (
                    <option key={pos} value={pos}>{pos}</option>
                  ))}
                </select>
              </div>

              {position === 'Other' && (
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">
                    Custom Position Note (e.g. Head of Marketing)
                  </label>
                  <input
                    type="text"
                    maxLength={60}
                    value={otherNote}
                    onChange={(e) => setOtherNote(e.target.value)}
                    placeholder="e.g. Head of Marketing"
                    className="w-full text-xs sm:text-sm bg-white border border-slate-300 rounded-xl px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#1b365d]/20 focus:border-[#1b365d]"
                  />
                  <p className="text-[11px] text-slate-400 mt-1">Letters, spaces, hyphens, and ampersands only (max 60 chars).</p>
                </div>
              )}

              <div className="bg-blue-50/70 border border-blue-200 rounded-xl p-3 text-xs text-blue-950">
                <p className="font-semibold mb-0.5">Note on Roles & Permissions:</p>
                <p className="text-slate-600 text-[11px] leading-relaxed">
                  Your position is used for document signature blocks and designation labels, not permissions.
                  Joining requires approval from <strong>{selectedClubForJoin.admin_name || 'the club administrator'}</strong> before private club files can be accessed.
                </p>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setSelectedClubForJoin(null)}
                  className="px-3.5 py-2 text-xs font-medium text-slate-600 hover:bg-slate-100 rounded-xl"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingJoin}
                  className="px-4 py-2 text-xs font-semibold text-white bg-[#1b365d] hover:bg-[#132742] rounded-xl shadow-sm disabled:opacity-50"
                >
                  {submittingJoin ? 'Submitting...' : 'Submit Join Request'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Create Club Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-60 bg-slate-900/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-lg w-full border border-slate-200 p-6">
            <h3 className="text-base font-bold text-slate-900">Add New Club</h3>
            <p className="text-xs text-slate-500 mt-1">
              Create a new student chapter. You will become its administrator immediately.
            </p>

            {createError && (
              <div className="mt-3 p-3 text-xs bg-red-50 border border-red-200 rounded-xl text-red-700">
                {createError}
              </div>
            )}

            <form onSubmit={handleCreateSubmit} className="mt-4 space-y-3.5">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">
                  Club Name *
                </label>
                <input
                  type="text"
                  required
                  value={newClubName}
                  onChange={(e) => setNewClubName(e.target.value)}
                  placeholder="e.g. Robotics Club, SVNIT"
                  className="w-full text-xs sm:text-sm bg-white border border-slate-300 rounded-xl px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#1b365d]/20 focus:border-[#1b365d]"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">
                    Short Name *
                  </label>
                  <input
                    type="text"
                    required
                    maxLength={50}
                    value={newClubShortName}
                    onChange={(e) => setNewClubShortName(e.target.value.toUpperCase())}
                    placeholder="e.g. ROBO"
                    className="w-full text-xs sm:text-sm bg-white border border-slate-300 rounded-xl px-3 py-2 text-slate-800 font-mono uppercase focus:outline-none focus:ring-2 focus:ring-[#1b365d]/20 focus:border-[#1b365d]"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">
                    Chapter Code (Optional)
                  </label>
                  <input
                    type="text"
                    maxLength={50}
                    value={newClubChapterCode}
                    onChange={(e) => setNewClubChapterCode(e.target.value.toUpperCase())}
                    placeholder="e.g. SVNIT-ROBO"
                    className="w-full text-xs sm:text-sm bg-white border border-slate-300 rounded-xl px-3 py-2 text-slate-800 font-mono uppercase focus:outline-none focus:ring-2 focus:ring-[#1b365d]/20 focus:border-[#1b365d]"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">
                  Your Position in this Club
                </label>
                <select
                  value={creatorPosition}
                  onChange={(e) => setCreatorPosition(e.target.value)}
                  className="w-full text-xs sm:text-sm bg-white border border-slate-300 rounded-xl px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#1b365d]/20 focus:border-[#1b365d]"
                >
                  {FIXED_POSITIONS.map((pos) => (
                    <option key={pos} value={pos}>{pos}</option>
                  ))}
                </select>
              </div>

              {creatorPosition === 'Other' && (
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">
                    Custom Position Note
                  </label>
                  <input
                    type="text"
                    maxLength={60}
                    value={creatorOtherNote}
                    onChange={(e) => setCreatorOtherNote(e.target.value)}
                    placeholder="e.g. Founder & Lead"
                    className="w-full text-xs sm:text-sm bg-white border border-slate-300 rounded-xl px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#1b365d]/20 focus:border-[#1b365d]"
                  />
                </div>
              )}

              {['Student Head/Chairperson', 'Student Secretary', 'Treasurer', 'Faculty Chairman', 'Faculty Co-Chairman'].includes(creatorPosition) && (
                <div className="flex items-center gap-2 pt-1">
                  <input
                    type="checkbox"
                    id="creatorSignatory"
                    checked={creatorIsSignatory}
                    onChange={(e) => setCreatorIsSignatory(e.target.checked)}
                    className="h-4 w-4 rounded border-slate-300 text-[#1b365d] focus:ring-[#1b365d]"
                  />
                  <label htmlFor="creatorSignatory" className="text-xs text-slate-700 font-medium cursor-pointer">
                    I sign official documents as {creatorPosition}
                  </label>
                </div>
              )}

              <div className="flex justify-end gap-2 pt-3">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-3.5 py-2 text-xs font-medium text-slate-600 hover:bg-slate-100 rounded-xl"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingCreate}
                  className="px-4 py-2 text-xs font-semibold text-white bg-[#1b365d] hover:bg-[#132742] rounded-xl shadow-sm disabled:opacity-50"
                >
                  {submittingCreate ? 'Creating...' : 'Create Club'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
