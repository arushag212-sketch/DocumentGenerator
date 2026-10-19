import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import { ClubSearchResult, JoinRequest } from '../types';
import {
  Building2,
  PlusCircle,
  Search,
  Clock,
  ArrowRight,
  CheckCircle2,
  AlertCircle,
  Users,
  PenLine,
  Eye,
  XCircle,
  Sparkles,
  ShieldCheck,
} from 'lucide-react';

type AccessLevel = 'editor' | 'viewer';

const POSITIONS = [
  'Executive Member',
  'Secretary',
  'Treasurer',
  'Chairperson',
  'Co-Chairperson',
  'Faculty Advisor',
  'Other',
];

const ACCESS_OPTIONS: { value: AccessLevel; title: string; body: string; icon: React.ReactNode }[] = [
  {
    value: 'editor',
    title: 'Editor',
    body: 'Create documents from a prompt, design templates with AI, and download DOCX/PDF.',
    icon: <PenLine className="w-4 h-4" />,
  },
  {
    value: 'viewer',
    title: 'Viewer',
    body: 'Read and download the club’s finalized documents only.',
    icon: <Eye className="w-4 h-4" />,
  },
];

const STATUS_POLL_MS = 8000;

// API timestamps are naive UTC; mark them as UTC so they render in local time.
const parseServerDate = (iso: string) => new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`);

// Free-text positions are stored as "Other: <title>" for signatory bookkeeping.
const displayPosition = (position: string) => position.replace(/^Other:\s*/, '');

function clubInitials(club: ClubSearchResult) {
  const short = (club.short_name || '').replace(/[^A-Za-z0-9]/g, '');
  if (short && short.length <= 4) return short.toUpperCase();
  const src = club.name;
  return src.replace(/[^A-Za-z0-9 ]/g, '').split(' ').filter(Boolean).slice(0, 2).map((w) => w[0]).join('').toUpperCase() || '?';
}

const ClubStatusBadge: React.FC<{ club: ClubSearchResult }> = ({ club }) => {
  if (club.membership_role) {
    return <span className="badge bg-emerald-50 text-emerald-700 border-emerald-200">Member · {club.membership_role}</span>;
  }
  if (club.join_request_status === 'pending') {
    return <span className="badge bg-amber-50 text-amber-700 border-amber-200">Request pending</span>;
  }
  if (club.join_request_status === 'rejected') {
    return <span className="badge bg-red-50 text-red-700 border-red-200">Not approved</span>;
  }
  return null;
};

export const OnboardingClubPage: React.FC = () => {
  const navigate = useNavigate();
  const { activeClub, refreshClubs, setActiveClubId } = useAuth();

  const [availableClubs, setAvailableClubs] = useState<ClubSearchResult[]>([]);
  const [clubsLoading, setClubsLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [mode, setMode] = useState<'join' | 'create'>('join');

  // Join form
  const [selectedClubId, setSelectedClubId] = useState<string>('');
  const [requestedPosition, setRequestedPosition] = useState('Executive Member');
  const [customPosition, setCustomPosition] = useState('');
  const [accessLevel, setAccessLevel] = useState<AccessLevel>('editor');
  const [joinMessage, setJoinMessage] = useState('');
  const [joinSubmitting, setJoinSubmitting] = useState(false);
  const [joinError, setJoinError] = useState<string | null>(null);

  // Request status (pending / rejected) for the club being tracked
  const [trackedRequest, setTrackedRequest] = useState<JoinRequest | null>(null);
  const [withdrawing, setWithdrawing] = useState(false);

  // Create form
  const [newClubName, setNewClubName] = useState('');
  const [newClubShortName, setNewClubShortName] = useState('');
  const [newClubChapterCode, setNewClubChapterCode] = useState('');
  const [newClubLogo, setNewClubLogo] = useState<File | null>(null);
  const [myPositionInNewClub, setMyPositionInNewClub] = useState('Student Head/Chairperson');
  const [createSubmitting, setCreateSubmitting] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const loadClubs = useCallback(() => {
    setClubsLoading(true);
    api.clubs
      .search('')
      .then((data) => setAvailableClubs(data || []))
      .catch(() => {})
      .finally(() => setClubsLoading(false));
  }, []);

  useEffect(loadClubs, [loadClubs]);

  // If the active club is one the user is still waiting on, show its status screen.
  useEffect(() => {
    if (!activeClub || activeClub.my_role) return;
    api.clubs
      .getMyJoinRequest(activeClub.id)
      .then((req) => {
        if (req && req.status === 'pending') setTrackedRequest(req);
      })
      .catch(() => {});
  }, [activeClub?.id, activeClub?.my_role]);

  // Poll the tracked request so approval unlocks the app without a manual refresh.
  useEffect(() => {
    if (!trackedRequest || trackedRequest.status !== 'pending') return;
    const timer = window.setInterval(async () => {
      try {
        const latest = await api.clubs.getMyJoinRequest(trackedRequest.club_id);
        if (!latest || latest.status === 'pending') return;
        if (latest.status === 'approved') {
          await refreshClubs();
          setActiveClubId(latest.club_id);
          navigate('/home', { replace: true });
          return;
        }
        setTrackedRequest(latest);
        await refreshClubs();
        loadClubs();
      } catch {
        /* transient; try again next tick */
      }
    }, STATUS_POLL_MS);
    return () => window.clearInterval(timer);
  }, [trackedRequest?.id, trackedRequest?.status]);

  const query = searchTerm.trim().toLowerCase();
  const filteredClubs = availableClubs.filter(
    (c) =>
      !query ||
      c.name.toLowerCase().includes(query) ||
      (c.short_name && c.short_name.toLowerCase().includes(query)) ||
      (c.chapter_code && c.chapter_code.toLowerCase().includes(query))
  );
  const selectedClub = availableClubs.find((c) => String(c.id) === String(selectedClubId)) || null;

  const handleSelectClub = (club: ClubSearchResult) => {
    setJoinError(null);
    if (club.membership_role) {
      setActiveClubId(club.id);
      navigate('/home');
      return;
    }
    setSelectedClubId(String(club.id));
  };

  const handleJoinSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedClubId) {
      setJoinError('Pick a club from the list first.');
      return;
    }
    const finalPosition = requestedPosition === 'Other' ? customPosition.trim() : requestedPosition;
    if (!finalPosition) {
      setJoinError('Tell the club admin your position.');
      return;
    }

    setJoinSubmitting(true);
    setJoinError(null);
    try {
      const req = await api.clubs.joinRequest(selectedClubId, {
        position: finalPosition,
        requested_role: accessLevel,
        message: joinMessage.trim() || undefined,
      });
      setTrackedRequest(req);
      await refreshClubs();
      setActiveClubId(selectedClubId);
      loadClubs();
    } catch (err: any) {
      setJoinError(err.message || 'Failed to submit join request.');
    } finally {
      setJoinSubmitting(false);
    }
  };

  const handleWithdraw = async () => {
    if (!trackedRequest) return;
    setWithdrawing(true);
    try {
      await api.clubs.cancelJoinRequest(trackedRequest.club_id, trackedRequest.id);
    } catch {
      /* already reviewed or gone; fall through to refresh */
    }
    setTrackedRequest(null);
    setSelectedClubId('');
    await refreshClubs();
    loadClubs();
    setWithdrawing(false);
  };

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newClubName.trim() || !newClubShortName.trim()) {
      setCreateError('Please enter club name and short acronym.');
      return;
    }
    if (!newClubLogo) {
      setCreateError('Please choose a club logo to use on official documents.');
      return;
    }
    if (!newClubLogo.type.startsWith('image/')) {
      setCreateError('Logo must be an image file.');
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
      await api.clubs.uploadLogo(created.id, newClubLogo);
      await refreshClubs();
      setActiveClubId(created.id);
      navigate('/home');
    } catch (err: any) {
      setCreateError(err.message || 'Failed to create club.');
    } finally {
      setCreateSubmitting(false);
    }
  };

  // ---------------- Status screen: pending or rejected ----------------
  if (trackedRequest && (trackedRequest.status === 'pending' || trackedRequest.status === 'rejected')) {
    const isRejected = trackedRequest.status === 'rejected';
    const accessLabel = trackedRequest.requested_role === 'viewer' ? 'Viewer' : 'Editor';
    return (
      <div className="max-w-xl mx-auto my-12 px-4">
        <div className={`surface-card p-8 sm:p-10 text-center relative overflow-hidden ${isRejected ? 'border-red-200' : 'border-amber-200'}`}>
          <div className={`absolute top-0 inset-x-0 h-1.5 ${isRejected ? 'bg-red-400' : 'bg-gradient-to-r from-amber-400 via-amber-500 to-amber-400 animate-pulse'}`} />
          <div
            className={`w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-5 ${
              isRejected ? 'bg-red-50 text-red-600' : 'bg-amber-50 text-amber-600'
            }`}
          >
            {isRejected ? <XCircle className="w-8 h-8" /> : <Clock className="w-8 h-8" />}
          </div>
          <h2 className="text-xl sm:text-2xl font-bold text-slate-900">
            {isRejected ? 'Request not approved' : 'Waiting for approval'}
          </h2>
          <p className="text-sm text-slate-600 mt-3 leading-relaxed">
            {isRejected ? (
              <>
                The admins of <span className="font-semibold text-slate-900">{trackedRequest.club_name}</span> didn’t approve
                this request. You can ask again after 24 hours, or join a different club.
              </>
            ) : (
              <>
                You asked to join <span className="font-semibold text-slate-900">{trackedRequest.club_name}</span> as{' '}
                <span className="font-semibold text-slate-900">{displayPosition(trackedRequest.position)}</span> with{' '}
                <span className="font-semibold text-slate-900">{accessLabel}</span> access.
              </>
            )}
          </p>

          <dl className="mt-6 p-4 bg-slate-50 border border-slate-200 rounded-2xl text-xs text-left divide-y divide-slate-200/70">
            <div className="flex justify-between py-1.5">
              <dt className="font-medium text-slate-600">Reviewer</dt>
              <dd className="text-slate-800">{trackedRequest.admin_name || 'Club owner / admin'}</dd>
            </div>
            <div className="flex justify-between py-1.5">
              <dt className="font-medium text-slate-600">Access requested</dt>
              <dd className="text-slate-800">{accessLabel}</dd>
            </div>
            <div className="flex justify-between py-1.5">
              <dt className="font-medium text-slate-600">Submitted</dt>
              <dd className="text-slate-800">{parseServerDate(trackedRequest.created_at).toLocaleString()}</dd>
            </div>
          </dl>

          {!isRejected && (
            <p className="text-xs text-slate-500 mt-4 flex items-center justify-center gap-1.5">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-amber-500" />
              </span>
              This page updates by itself as soon as an admin responds.
            </p>
          )}

          <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-3">
            {!isRejected && (
              <button type="button" onClick={handleWithdraw} disabled={withdrawing} className="btn-secondary w-full sm:w-auto">
                {withdrawing ? 'Withdrawing…' : 'Withdraw request'}
              </button>
            )}
            <button
              type="button"
              onClick={() => {
                setTrackedRequest(null);
                setSelectedClubId('');
              }}
              className="btn-primary w-full sm:w-auto"
            >
              Join a different club
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ---------------- Main onboarding ----------------
  return (
    <div className="max-w-6xl mx-auto my-8 px-4 sm:px-6">
      <div className="text-center max-w-2xl mx-auto mb-8">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-50 border border-blue-200 text-[#1b365d] text-xs font-semibold mb-3">
          <Building2 className="w-3.5 h-3.5" />
          <span>Step 1 of 2 · Your club</span>
        </div>
        <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">Which club do you work with?</h1>
        <p className="text-sm text-slate-500 mt-2">
          Ask to join an existing club — an owner or admin approves you — or register a new club and become its owner.
        </p>
      </div>

      <div className="flex justify-center mb-6">
        <div className="inline-flex p-1 bg-slate-100 rounded-xl border border-slate-200" role="tablist">
          {(['join', 'create'] as const).map((m) => (
            <button
              key={m}
              type="button"
              role="tab"
              aria-selected={mode === m}
              onClick={() => setMode(m)}
              className={`px-4 sm:px-6 py-2 text-xs sm:text-sm font-semibold rounded-lg transition-all ${
                mode === m ? 'bg-white text-[#1b365d] shadow-sm' : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              {m === 'join' ? 'Join a club' : 'Register a new club'}
            </button>
          ))}
        </div>
      </div>

      {mode === 'join' ? (
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6 items-start">
          {/* Club directory */}
          <section className="lg:col-span-3 surface-card p-5 sm:p-6">
            <div className="relative mb-4">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="search"
                placeholder="Search clubs by name, acronym or chapter code"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="input-field pl-9"
                aria-label="Search clubs"
              />
            </div>

            {clubsLoading ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {[0, 1, 2, 3].map((i) => (
                  <div key={i} className="h-24 rounded-2xl bg-slate-100 animate-pulse" />
                ))}
              </div>
            ) : filteredClubs.length === 0 ? (
              <div className="text-center py-12">
                <Building2 className="w-10 h-10 text-slate-300 mx-auto mb-2" />
                <p className="text-sm font-semibold text-slate-700">No club matches “{searchTerm}”</p>
                <button type="button" onClick={() => setMode('create')} className="text-xs font-semibold text-[#1b365d] hover:underline mt-2">
                  Register it as a new club →
                </button>
              </div>
            ) : (
              <ul className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-h-[460px] overflow-y-auto pr-1">
                {filteredClubs.map((club) => {
                  const selected = String(club.id) === String(selectedClubId);
                  return (
                    <li key={club.id}>
                      <button
                        type="button"
                        onClick={() => handleSelectClub(club)}
                        aria-pressed={selected}
                        className={`w-full text-left p-4 rounded-2xl border transition-all flex items-start gap-3 ${
                          selected
                            ? 'border-[#1b365d] bg-blue-50/60 ring-2 ring-[#1b365d]/20'
                            : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50'
                        }`}
                      >
                        <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-[#1b365d] to-[#2c5282] text-white flex items-center justify-center font-bold text-sm flex-shrink-0">
                          {clubInitials(club)}
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-bold text-slate-900 truncate">{club.name}</p>
                          <p className="text-[11px] text-slate-500 mt-0.5 flex items-center gap-1 whitespace-nowrap">
                            <Users className="w-3 h-3 flex-shrink-0" />
                            {club.members_count} member{club.members_count === 1 ? '' : 's'}
                          </p>
                          {club.admin_name && (
                            <p className="text-[11px] text-slate-400 truncate">Admin: {club.admin_name}</p>
                          )}
                          <div className="mt-2">
                            <ClubStatusBadge club={club} />
                            {club.membership_role && (
                              <span className="text-[11px] font-semibold text-[#1b365d] ml-2">Open →</span>
                            )}
                          </div>
                        </div>
                        {selected && <CheckCircle2 className="w-5 h-5 text-[#1b365d] flex-shrink-0" />}
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>

          {/* Request form */}
          <section className="lg:col-span-2 surface-card p-5 sm:p-6 lg:sticky lg:top-24">
            <h2 className="text-base font-bold text-slate-900">Request to join</h2>
            <p className="text-xs text-slate-500 mt-0.5 mb-5">
              {selectedClub ? (
                <>
                  Sending to <span className="font-semibold text-slate-800">{selectedClub.name}</span>
                </>
              ) : (
                'Select a club on the left.'
              )}
            </p>

            <form onSubmit={handleJoinSubmit} className="space-y-4">
              {joinError && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700 flex items-start gap-2" role="alert">
                  <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                  <span>{joinError}</span>
                </div>
              )}

              <fieldset>
                <legend className="field-label">Access you need</legend>
                <div className="grid grid-cols-1 gap-2">
                  {ACCESS_OPTIONS.map((opt) => (
                    <label
                      key={opt.value}
                      className={`flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition-colors ${
                        accessLevel === opt.value ? 'border-[#1b365d] bg-blue-50/50' : 'border-slate-200 hover:bg-slate-50'
                      }`}
                    >
                      <input
                        type="radio"
                        name="access"
                        value={opt.value}
                        checked={accessLevel === opt.value}
                        onChange={() => setAccessLevel(opt.value)}
                        className="mt-1 accent-[#1b365d]"
                      />
                      <span>
                        <span className="flex items-center gap-1.5 text-sm font-semibold text-slate-900">
                          {opt.icon}
                          {opt.title}
                        </span>
                        <span className="block text-[11px] text-slate-500 mt-0.5 leading-snug">{opt.body}</span>
                      </span>
                    </label>
                  ))}
                </div>
              </fieldset>

              <div>
                <label htmlFor="join-position" className="field-label">Your position in the club</label>
                <select
                  id="join-position"
                  value={requestedPosition}
                  onChange={(e) => setRequestedPosition(e.target.value)}
                  className="input-field"
                >
                  {POSITIONS.map((p) => (
                    <option key={p} value={p}>
                      {p === 'Other' ? 'Other (custom title)' : p}
                    </option>
                  ))}
                </select>
              </div>

              {requestedPosition === 'Other' && (
                <div>
                  <label htmlFor="join-custom-position" className="field-label">Position title</label>
                  <input
                    id="join-custom-position"
                    type="text"
                    placeholder="e.g. Event Coordinator"
                    value={customPosition}
                    onChange={(e) => setCustomPosition(e.target.value)}
                    required
                    className="input-field"
                  />
                </div>
              )}

              <div>
                <label htmlFor="join-message" className="field-label">
                  Note to the admin <span className="font-normal text-slate-400">(optional)</span>
                </label>
                <textarea
                  id="join-message"
                  rows={2}
                  maxLength={500}
                  placeholder="e.g. I’m handling sponsorship letters for TechFest."
                  value={joinMessage}
                  onChange={(e) => setJoinMessage(e.target.value)}
                  className="input-field resize-none"
                />
              </div>

              <button type="submit" disabled={joinSubmitting || !selectedClub} className="btn-primary w-full">
                {joinSubmitting ? 'Sending request…' : 'Send join request'}
                <ArrowRight className="w-4 h-4" />
              </button>
              <p className="text-[11px] text-slate-400 flex items-start gap-1.5">
                <ShieldCheck className="w-3.5 h-3.5 flex-shrink-0 mt-px" />
                You’ll get access once a club owner or admin approves. They can grant a different access level.
              </p>
            </form>
          </section>
        </div>
      ) : (
        <section className="max-w-2xl mx-auto surface-card p-6 sm:p-8">
          <div className="flex items-center gap-3 mb-5">
            <div className="w-12 h-12 bg-emerald-50 text-emerald-600 rounded-2xl flex items-center justify-center">
              <PlusCircle className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-900">Register a new club</h2>
              <p className="text-xs text-slate-500">You become its owner and approve who else can create documents.</p>
            </div>
          </div>

          <form onSubmit={handleCreateSubmit} className="space-y-4">
            {createError && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700 flex items-start gap-2" role="alert">
                <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                <span>{createError}</span>
              </div>
            )}

            <div>
              <label htmlFor="club-name" className="field-label">Full club name</label>
              <input
                id="club-name"
                type="text"
                placeholder="e.g. Developer Students Club"
                value={newClubName}
                onChange={(e) => setNewClubName(e.target.value)}
                required
                className="input-field"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label htmlFor="club-short" className="field-label">Short acronym</label>
                <input
                  id="club-short"
                  type="text"
                  placeholder="e.g. DSC"
                  value={newClubShortName}
                  onChange={(e) => setNewClubShortName(e.target.value)}
                  required
                  className="input-field uppercase"
                />
              </div>
              <div>
                <label htmlFor="club-code" className="field-label">
                  Chapter code <span className="font-normal text-slate-400">(optional)</span>
                </label>
                <input
                  id="club-code"
                  type="text"
                  placeholder="e.g. GDSC-SVNIT"
                  value={newClubChapterCode}
                  onChange={(e) => setNewClubChapterCode(e.target.value)}
                  className="input-field uppercase"
                />
              </div>
            </div>

            <div>
              <label htmlFor="club-logo" className="field-label">Club logo</label>
              <input
                id="club-logo"
                type="file"
                accept="image/png,image/jpeg,image/webp"
                required
                onChange={(e) => setNewClubLogo(e.target.files?.[0] || null)}
                className="w-full text-xs text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-emerald-50 file:px-3 file:py-2 file:text-xs file:font-semibold file:text-emerald-700 hover:file:bg-emerald-100"
              />
              <p className="text-[11px] text-slate-400 mt-1">PNG, JPEG or WebP, up to 2 MB. Used on the club letterhead.</p>
            </div>

            <div>
              <label htmlFor="club-position" className="field-label">Your position in this club</label>
              <input
                id="club-position"
                type="text"
                value={myPositionInNewClub}
                onChange={(e) => setMyPositionInNewClub(e.target.value)}
                required
                className="input-field"
              />
            </div>

            <button
              type="submit"
              disabled={createSubmitting}
              className="btn-primary w-full !bg-emerald-600 hover:!bg-emerald-700"
            >
              {createSubmitting ? 'Registering club…' : 'Register club & start'}
              <Sparkles className="w-4 h-4" />
            </button>
          </form>
        </section>
      )}
    </div>
  );
};
