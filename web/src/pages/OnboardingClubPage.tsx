import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import { ClubSearchResult, JoinRequest } from '../types';
import { Building2, PlusCircle, Search, Clock, ArrowRight, CheckCircle2, AlertCircle } from 'lucide-react';

export const OnboardingClubPage: React.FC = () => {
  const navigate = useNavigate();
  const { activeClub, refreshClubs, setActiveClubId } = useAuth();

  const [availableClubs, setAvailableClubs] = useState<ClubSearchResult[]>([]);
  const [searchTerm, setSearchTerm] = useState('');

  // Join Existing Club Form
  const [selectedClubId, setSelectedClubId] = useState<string>('');
  const [requestedPosition, setRequestedPosition] = useState('Executive Member');
  const [customPosition, setCustomPosition] = useState('');
  const [joinSubmitting, setJoinSubmitting] = useState(false);
  const [joinError, setJoinError] = useState<string | null>(null);
  const [pendingRequest, setPendingRequest] = useState<JoinRequest | null>(null);

  // Register New Club Form
  const [newClubName, setNewClubName] = useState('');
  const [newClubShortName, setNewClubShortName] = useState('');
  const [newClubChapterCode, setNewClubChapterCode] = useState('');
  const [myPositionInNewClub, setMyPositionInNewClub] = useState('Chairperson');
  const [createSubmitting, setCreateSubmitting] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  // Check if current user already has pending request in activeClub or any club
  useEffect(() => {
    if (activeClub) {
      api.clubs.getMyJoinRequest(activeClub.id)
        .then((req) => {
          if (req && req.status === 'pending') {
            setPendingRequest(req);
          }
        })
        .catch(() => {});
    }
  }, [activeClub]);

  // Load available clubs for search across institute
  useEffect(() => {
    api.clubs.search('')
      .then((data) => {
        setAvailableClubs(data || []);
      })
      .catch(() => {});
  }, []);

  const filteredClubs = availableClubs.filter(
    (c) =>
      c.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (c.short_name && c.short_name.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  const handleJoinSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedClubId) {
      setJoinError('Please select a club to join.');
      return;
    }
    const finalPosition = requestedPosition === 'Other' ? customPosition.trim() : requestedPosition;
    if (!finalPosition) {
      setJoinError('Please specify your position or role.');
      return;
    }

    setJoinSubmitting(true);
    setJoinError(null);
    try {
      const req = await api.clubs.joinRequest(selectedClubId, { position: finalPosition });
      setPendingRequest(req);
      await refreshClubs();
      setActiveClubId(selectedClubId);
    } catch (err: any) {
      setJoinError(err.message || 'Failed to submit join request.');
    } finally {
      setJoinSubmitting(false);
    }
  };

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newClubName.trim() || !newClubShortName.trim()) {
      setCreateError('Please enter club name and short acronym.');
      return;
    }

    setCreateSubmitting(true);
    setCreateError(null);
    try {
      const created = await api.clubs.createClub({
        name: newClubName.trim(),
        short_name: newClubShortName.trim().toUpperCase(),
        chapter_code: newClubChapterCode.trim() || undefined,
        position: myPositionInNewClub.trim() || 'Chairperson',
        is_signatory: true,
      });
      await refreshClubs();
      setActiveClubId(created.id);
      navigate('/home');
    } catch (err: any) {
      setCreateError(err.message || 'Failed to create club.');
    } finally {
      setCreateSubmitting(false);
    }
  };

  if (pendingRequest) {
    const targetClub = availableClubs.find((c) => String(c.id) === String(pendingRequest.club_id)) || activeClub;
    return (
      <div className="max-w-xl mx-auto my-12 px-4">
        <div className="bg-white border border-amber-200 rounded-3xl p-8 sm:p-10 shadow-lg text-center relative overflow-hidden">
          <div className="absolute top-0 left-0 right-0 h-2 bg-gradient-to-r from-amber-400 to-amber-500" />
          <div className="w-16 h-16 bg-amber-50 text-amber-600 rounded-2xl flex items-center justify-center mx-auto mb-5 shadow-inner">
            <Clock className="w-8 h-8 animate-pulse" />
          </div>
          <h2 className="text-xl sm:text-2xl font-bold text-slate-900">Waiting for Club Approval</h2>
          <p className="text-sm text-slate-600 mt-3 leading-relaxed">
            Your request to join <span className="font-semibold text-slate-900">{targetClub?.name || 'the club'}</span> as{' '}
            <span className="font-semibold text-slate-900">{pendingRequest.position}</span> has been submitted.
          </p>
          <div className="mt-5 p-4 bg-slate-50 border border-slate-200 rounded-2xl text-xs text-slate-500 text-left">
            <div className="flex justify-between py-1 border-b border-slate-100">
              <span className="font-medium text-slate-600">Reviewer:</span>
              <span>{pendingRequest.admin_name || 'Club Head / Administrator'}</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-100">
              <span className="font-medium text-slate-600">Status:</span>
              <span className="text-amber-600 font-semibold uppercase tracking-wider text-[11px]">Pending Review</span>
            </div>
            <div className="flex justify-between py-1">
              <span className="font-medium text-slate-600">Submitted:</span>
              <span>{new Date(pendingRequest.created_at).toLocaleDateString()}</span>
            </div>
          </div>
          <p className="text-xs text-slate-400 mt-4">
            Once approved by the club administrator, you will immediately unlock drafting official club documents.
          </p>
          <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-3">
            <button
              type="button"
              onClick={() => {
                setPendingRequest(null);
                setSelectedClubId('');
              }}
              className="w-full sm:w-auto px-5 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-semibold rounded-xl transition-colors"
            >
              Choose another club
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto my-8 px-4 sm:px-6">
      <div className="text-center max-w-2xl mx-auto mb-10">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-50 border border-blue-200 text-[#1b365d] text-xs font-semibold mb-3">
          <Building2 className="w-3.5 h-3.5" />
          <span>SVNIT Student Chapters & Clubs</span>
        </div>
        <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900">Get Started with Your Club</h1>
        <p className="text-sm text-slate-500 mt-2">
          Join an active student club to collaborate on official institute letters, or register a new club as its administrator.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8 items-start">
        {/* Card 1: Join Existing Club */}
        <div className="bg-white border border-slate-200 rounded-3xl p-6 sm:p-8 shadow-sm hover:shadow-md transition-shadow">
          <div className="flex items-center gap-3 mb-5">
            <div className="w-12 h-12 bg-blue-50 text-[#1b365d] rounded-2xl flex items-center justify-center">
              <Search className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-900">Join an Existing Club</h2>
              <p className="text-xs text-slate-500">Request membership in an established chapter</p>
            </div>
          </div>

          <form onSubmit={handleJoinSubmit} className="space-y-4">
            {joinError && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700 flex items-start gap-2">
                <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                <span>{joinError}</span>
              </div>
            )}

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">Search or Select Club</label>
              <div className="relative mb-2">
                <input
                  type="text"
                  placeholder="Filter by name or code..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full text-xs pl-8 pr-3 py-2 border border-slate-200 rounded-xl focus:ring-2 focus:ring-[#1b365d] focus:outline-none"
                />
                <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5" />
              </div>

              <select
                value={selectedClubId}
                onChange={(e) => setSelectedClubId(e.target.value)}
                required
                className="w-full text-xs sm:text-sm px-3 py-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-[#1b365d] focus:outline-none bg-white text-slate-800"
              >
                <option value="">-- Choose a club ({filteredClubs.length} available) --</option>
                {filteredClubs.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} {c.short_name ? `(${c.short_name})` : ''}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">Your Position in Club</label>
              <select
                value={requestedPosition}
                onChange={(e) => setRequestedPosition(e.target.value)}
                className="w-full text-xs sm:text-sm px-3 py-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-[#1b365d] focus:outline-none bg-white text-slate-800"
              >
                <option value="Executive Member">Executive Member</option>
                <option value="Secretary">Secretary</option>
                <option value="Treasurer">Treasurer</option>
                <option value="Chairperson">Chairperson</option>
                <option value="Co-Chairperson">Co-Chairperson</option>
                <option value="Faculty Advisor">Faculty Advisor</option>
                <option value="Other">Other (Custom Title)</option>
              </select>
            </div>

            {requestedPosition === 'Other' && (
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Specify Position Title</label>
                <input
                  type="text"
                  placeholder="e.g. Lead Developer, Event Coordinator"
                  value={customPosition}
                  onChange={(e) => setCustomPosition(e.target.value)}
                  required
                  className="w-full text-xs sm:text-sm px-3 py-2 border border-slate-200 rounded-xl focus:ring-2 focus:ring-[#1b365d] focus:outline-none"
                />
              </div>
            )}

            <button
              type="submit"
              disabled={joinSubmitting}
              className="w-full mt-2 py-2.5 px-4 bg-[#1b365d] hover:bg-[#132742] text-white text-xs sm:text-sm font-bold rounded-xl transition-colors shadow-sm flex items-center justify-center gap-2 disabled:opacity-50"
            >
              {joinSubmitting ? 'Submitting...' : 'Submit Join Request'}
              <ArrowRight className="w-4 h-4" />
            </button>
          </form>
        </div>

        {/* Card 2: Register New Club */}
        <div className="bg-white border border-slate-200 rounded-3xl p-6 sm:p-8 shadow-sm hover:shadow-md transition-shadow">
          <div className="flex items-center gap-3 mb-5">
            <div className="w-12 h-12 bg-emerald-50 text-emerald-600 rounded-2xl flex items-center justify-center">
              <PlusCircle className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-900">Register a New Club</h2>
              <p className="text-xs text-slate-500">Create a chapter and become its Administrator</p>
            </div>
          </div>

          <form onSubmit={handleCreateSubmit} className="space-y-4">
            {createError && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700 flex items-start gap-2">
                <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                <span>{createError}</span>
              </div>
            )}

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Full Club Name</label>
              <input
                type="text"
                placeholder="e.g. Developer Students Club"
                value={newClubName}
                onChange={(e) => setNewClubName(e.target.value)}
                required
                className="w-full text-xs sm:text-sm px-3 py-2 border border-slate-200 rounded-xl focus:ring-2 focus:ring-[#1b365d] focus:outline-none"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Short Acronym</label>
                <input
                  type="text"
                  placeholder="e.g. DSC"
                  value={newClubShortName}
                  onChange={(e) => setNewClubShortName(e.target.value)}
                  required
                  className="w-full text-xs sm:text-sm px-3 py-2 border border-slate-200 rounded-xl focus:ring-2 focus:ring-[#1b365d] focus:outline-none uppercase"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Chapter Code (Opt)</label>
                <input
                  type="text"
                  placeholder="e.g. GDSC-SVNIT"
                  value={newClubChapterCode}
                  onChange={(e) => setNewClubChapterCode(e.target.value)}
                  className="w-full text-xs sm:text-sm px-3 py-2 border border-slate-200 rounded-xl focus:ring-2 focus:ring-[#1b365d] focus:outline-none uppercase"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Your Role in this Club</label>
              <input
                type="text"
                value={myPositionInNewClub}
                onChange={(e) => setMyPositionInNewClub(e.target.value)}
                required
                className="w-full text-xs sm:text-sm px-3 py-2 border border-slate-200 rounded-xl focus:ring-2 focus:ring-[#1b365d] focus:outline-none"
              />
              <p className="text-[11px] text-slate-400 mt-1">
                You will automatically become the club owner and administrator.
              </p>
            </div>

            <button
              type="submit"
              disabled={createSubmitting}
              className="w-full mt-2 py-2.5 px-4 bg-emerald-600 hover:bg-emerald-700 text-white text-xs sm:text-sm font-bold rounded-xl transition-colors shadow-sm flex items-center justify-center gap-2 disabled:opacity-50"
            >
              {createSubmitting ? 'Registering Club...' : 'Register & Start Drafting'}
              <CheckCircle2 className="w-4 h-4" />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};
