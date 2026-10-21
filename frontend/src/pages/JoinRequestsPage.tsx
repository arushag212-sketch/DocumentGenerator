import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import { JoinRequest, ClubPosition } from '../types';
import { CheckCircle2, XCircle, Clock, AlertCircle, RefreshCw, Shield } from 'lucide-react';

const FALLBACK_POSITIONS: ClubPosition[] = [
  { key: 'faculty_chairman', label: 'Faculty Chairman', group: 'faculty', signs: true, help: "Signs approval notes and bills as the club's faculty chairman." },
  { key: 'faculty_co_chairman', label: 'Faculty Co-Chairman', group: 'faculty', signs: true, help: "Second faculty signatory on approval notes." },
  { key: 'faculty_incharge', label: 'Faculty In-charge (venue)', group: 'faculty', signs: false, help: "Named on permission letters for a venue they look after." },
  { key: 'student_head', label: 'Student Head/Chairperson', group: 'student', signs: true, help: "Signs letters and receipts on behalf of the students." },
  { key: 'student_secretary', label: 'Student Secretary', group: 'student', signs: true, help: "Co-signs letters with the student head." },
  { key: 'treasurer', label: 'Treasurer', group: 'student', signs: true, help: "Signs bill summaries and certificates of expenditure." },
  { key: 'technical_assistant', label: 'Technical Assistant', group: 'staff', signs: false, help: "Named on permission letters for labs and halls." },
  { key: 'other', label: 'Other', group: 'other', signs: false, help: "Any other position; give it a designation." },
];

export const JoinRequestsPage: React.FC = () => {
  const { activeClub } = useAuth();
  const [requests, setRequests] = useState<JoinRequest[]>([]);
  const [positions, setPositions] = useState<ClubPosition[]>([]);
  const [loading, setLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [processingId, setProcessingId] = useState<string | null>(null);
  const [selectedRoles, setSelectedRoles] = useState<Record<string, string>>({});
  const [selectedPositions, setSelectedPositions] = useState<Record<string, string>>({});
  const [customPositions, setCustomPositions] = useState<Record<string, string>>({});
  const [selectedSignatories, setSelectedSignatories] = useState<Record<string, boolean>>({});

  const loadPositions = async () => {
    if (!activeClub) return;
    try {
      const data = await api.clubs.getPositions(activeClub.id);
      setPositions(data && data.length > 0 ? data : FALLBACK_POSITIONS);
    } catch {
      setPositions(FALLBACK_POSITIONS);
    }
  };

  const loadRequests = async () => {
    if (!activeClub) return;
    setLoading(true);
    setActionError(null);
    try {
      const data = await api.clubs.listJoinRequests(activeClub.id);
      setRequests(data || []);
      // Set default role and position mapping for new requests
      const initialRoles: Record<string, string> = {};
      const initialPositions: Record<string, string> = {};
      const initialCustomPositions: Record<string, string> = {};
      (data || []).forEach((r) => {
        initialRoles[r.id] = r.requested_role || 'editor';
        if (r.position.toLowerCase().startsWith('other:')) {
          initialPositions[r.id] = 'Other';
          initialCustomPositions[r.id] = r.position.split(':', 2)[1].trim();
        } else if (r.position.toLowerCase() === 'other') {
          initialPositions[r.id] = 'Other';
          initialCustomPositions[r.id] = '';
        } else {
          initialPositions[r.id] = r.position;
          initialCustomPositions[r.id] = '';
        }
      });
      setSelectedRoles(initialRoles);
      setSelectedPositions(initialPositions);
      setCustomPositions(initialCustomPositions);
    } catch (err: any) {
      setActionError(err.message || 'Failed to load join requests.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRequests();
    loadPositions();
  }, [activeClub?.id]);

  const activePositionsList = positions.length > 0 ? positions : FALLBACK_POSITIONS;

  const getEffectivePosition = (req: JoinRequest) => {
    const sel = selectedPositions[req.id] ?? (req.position.toLowerCase().startsWith('other:') ? 'Other' : req.position);
    if (sel === 'Other') {
      const custom = (customPositions[req.id] ?? (req.position.toLowerCase().startsWith('other:') ? req.position.split(':', 2)[1].trim() : '')).trim();
      return custom ? `Other: ${custom}` : 'Other';
    }
    return sel;
  };

  const handleApprove = async (req: JoinRequest) => {
    if (!activeClub) return;
    const assignedRole = selectedRoles[req.id] || req.requested_role || 'editor';
    const effectivePos = getEffectivePosition(req);
    const selPos = selectedPositions[req.id] ?? (req.position.toLowerCase().startsWith('other:') ? 'Other' : req.position);
    const matchedPos = activePositionsList.find(
      (p) => p.label.toLowerCase() === selPos.toLowerCase() || p.key.toLowerCase() === selPos.toLowerCase()
    );
    const isSignatoryEligible = selPos !== 'Other' && Boolean(matchedPos?.signs);
    const isSignatory = isSignatoryEligible && Boolean(selectedSignatories[req.id]);

    setProcessingId(req.id);
    setActionError(null);
    setActionSuccess(null);
    try {
      await api.clubs.approveJoinRequest(activeClub.id, req.id, {
        role: assignedRole,
        position: effectivePos,
        is_signatory: isSignatory,
      });
      setActionSuccess(`Approved ${req.user_name || req.user_email} as ${assignedRole} (${effectivePos}).`);
      await loadRequests();
    } catch (err: any) {
      setActionError(err.message || 'Failed to approve join request.');
    } finally {
      setProcessingId(null);
    }
  };

  const handleReject = async (req: JoinRequest) => {
    if (!activeClub) return;
    if (!window.confirm(`Reject join request from ${req.user_name || req.user_email}?`)) return;
    setProcessingId(req.id);
    setActionError(null);
    setActionSuccess(null);
    try {
      await api.clubs.rejectJoinRequest(activeClub.id, req.id);
      setActionSuccess(`Rejected request from ${req.user_name || req.user_email}.`);
      await loadRequests();
    } catch (err: any) {
      setActionError(err.message || 'Failed to reject request.');
    } finally {
      setProcessingId(null);
    }
  };

  const pendingRequests = requests.filter((r) => r.status === 'pending');
  const pastRequests = requests.filter((r) => r.status !== 'pending');

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-8 py-8">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-8">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-brand-50 border border-brand-200 text-brand-700 text-xs font-semibold mb-2">
            <Shield className="w-3.5 h-3.5" />
            <span>Club Administration</span>
          </div>
          <h1 className="text-2xl font-bold text-slate-900">Membership Join Requests</h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            Review and grant club access permissions for pending member registrations in {activeClub?.name}.
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            loadRequests();
            loadPositions();
          }}
          disabled={loading}
          className="px-3.5 py-2 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 text-xs font-semibold rounded-xl flex items-center gap-1.5 transition-colors shadow-sm disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {actionSuccess && (
        <div className="mb-6 p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-xs text-emerald-800 flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
          <span>{actionSuccess}</span>
        </div>
      )}

      {actionError && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-red-600 flex-shrink-0" />
          <span>{actionError}</span>
        </div>
      )}

      {/* Pending Requests Section */}
      <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm mb-8">
        <div className="flex items-center justify-between pb-4 border-b border-slate-100 mb-5">
          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4 text-amber-500" />
            <h2 className="text-base font-bold text-slate-900">Pending Approval ({pendingRequests.length})</h2>
          </div>
        </div>

        {loading && requests.length === 0 ? (
          <div className="text-center py-12 text-slate-400 text-xs">Loading pending requests...</div>
        ) : pendingRequests.length === 0 ? (
          <div className="text-center py-12">
            <CheckCircle2 className="w-10 h-10 text-emerald-500 mx-auto mb-2 opacity-80" />
            <p className="text-sm font-semibold text-slate-700">All caught up!</p>
            <p className="text-xs text-slate-400 mt-0.5">No pending membership requests waiting for review.</p>
          </div>
        ) : (
          <div className="space-y-5">
            {pendingRequests.map((req) => {
              const currentPosSelection = selectedPositions[req.id] ?? (req.position.toLowerCase().startsWith('other:') ? 'Other' : req.position);
              const effectivePos = getEffectivePosition(req);
              const isChanged = effectivePos !== req.position;

              const matchedPos = activePositionsList.find(
                (p) => p.label.toLowerCase() === currentPosSelection.toLowerCase() || p.key.toLowerCase() === currentPosSelection.toLowerCase()
              );
              const isSignatoryEligible = currentPosSelection !== 'Other' && Boolean(matchedPos?.signs);

              // Check if req.position is among known positions list
              const isReqPosInCatalog = activePositionsList.some(
                (p) => p.label.toLowerCase() === req.position.toLowerCase() || p.key.toLowerCase() === req.position.toLowerCase()
              );
              const isReqPosOther = req.position.toLowerCase() === 'other' || req.position.toLowerCase().startsWith('other:');

              return (
                <div
                  key={req.id}
                  className="flex flex-col lg:flex-row items-start lg:items-center justify-between p-4 bg-slate-50/70 border border-slate-200 rounded-xl gap-4"
                >
                  <div className="flex items-start gap-3">
                    <div className="w-10 h-10 rounded-xl bg-brand-100 text-brand-700 flex items-center justify-center font-bold text-sm flex-shrink-0">
                      {(req.user_name || req.user_email || 'U')[0].toUpperCase()}
                    </div>
                    <div>
                      <h3 className="text-sm font-bold text-slate-900">{req.user_name || 'Member'}</h3>
                      <p className="text-xs text-slate-500">{req.user_email}</p>
                      <div className="flex flex-wrap items-center gap-2 mt-2">
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-semibold bg-brand-50 text-brand-700 border border-brand-200">
                          Requested position: {req.position}
                        </span>
                        <span
                          className={`badge ${
                            req.requested_role === 'viewer'
                              ? 'bg-slate-100 text-slate-700 border-slate-200'
                              : 'bg-emerald-50 text-emerald-700 border-emerald-200'
                          }`}
                        >
                          Requested access: {req.requested_role === 'viewer' ? 'Viewer (read-only)' : 'Editor (create documents)'}
                        </span>
                        <span className="text-xs text-slate-400">
                          Submitted: {new Date(req.created_at).toLocaleDateString()}
                        </span>
                      </div>
                      {req.message && (
                        <p className="mt-2 text-xs text-slate-600 bg-white border border-slate-200 rounded-lg px-3 py-2 max-w-md italic">
                          “{req.message}”
                        </p>
                      )}
                    </div>
                  </div>

                  <div className="flex flex-col items-start lg:items-end gap-2 w-full lg:w-auto border-t lg:border-t-0 pt-3 lg:pt-0">
                    <div className="flex flex-wrap items-center gap-2 w-full lg:w-auto">
                      {/* Access Role Selector */}
                      <div className="flex flex-col">
                        <label className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1">
                          Access Role
                        </label>
                        <select
                          value={selectedRoles[req.id] || req.requested_role || 'editor'}
                          onChange={(e) =>
                            setSelectedRoles({
                              ...selectedRoles,
                              [req.id]: e.target.value,
                            })
                          }
                          aria-label={`Access to grant ${req.user_name || req.user_email}`}
                          className="text-xs px-2.5 py-2 border border-slate-200 rounded-xl bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-brand-700"
                        >
                          <option value="editor">Editor — create documents &amp; templates</option>
                          <option value="viewer">Viewer — read only</option>
                          <option value="admin">Admin — also approve members</option>
                        </select>
                      </div>

                      {/* Club Position Selector */}
                      <div className="flex flex-col">
                        <label className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1">
                          Club Position
                        </label>
                        <select
                          value={currentPosSelection}
                          onChange={(e) =>
                            setSelectedPositions({
                              ...selectedPositions,
                              [req.id]: e.target.value,
                            })
                          }
                          aria-label={`Club position for ${req.user_name || req.user_email}`}
                          className="text-xs px-2.5 py-2 border border-slate-200 rounded-xl bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-brand-700"
                        >
                          {!isReqPosInCatalog && !isReqPosOther && (
                            <option value={req.position}>{req.position}</option>
                          )}
                          {activePositionsList.map((p) => (
                            <option key={p.key} value={p.label}>
                              {p.label}
                            </option>
                          ))}
                        </select>
                      </div>

                      {/* Actions */}
                      <div className="flex items-center gap-2 self-end">
                        <button
                          type="button"
                          onClick={() => handleApprove(req)}
                          disabled={processingId === req.id}
                          className="px-4 py-2 bg-brand-700 hover:bg-brand-800 text-white text-xs font-bold rounded-xl transition-colors shadow-sm flex items-center gap-1.5 disabled:opacity-50"
                        >
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          <span>Approve</span>
                        </button>

                        <button
                          type="button"
                          onClick={() => handleReject(req)}
                          disabled={processingId === req.id}
                          className="px-3 py-2 bg-white hover:bg-red-50 text-red-600 border border-slate-200 hover:border-red-200 text-xs font-semibold rounded-xl transition-colors flex items-center gap-1 disabled:opacity-50"
                        >
                          <XCircle className="w-3.5 h-3.5" />
                          <span>Reject</span>
                        </button>
                      </div>
                    </div>

                    {/* If "Other" chosen, show custom title box */}
                    {currentPosSelection === 'Other' && (
                      <div className="w-full flex items-center gap-2 mt-1">
                        <input
                          type="text"
                          placeholder="Specify custom position title (e.g. Event Lead)"
                          value={customPositions[req.id] ?? ''}
                          onChange={(e) =>
                            setCustomPositions({
                              ...customPositions,
                              [req.id]: e.target.value,
                            })
                          }
                          className="text-xs px-3 py-1.5 border border-slate-200 rounded-xl bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-brand-700 w-full max-w-xs"
                        />
                      </div>
                    )}

                    {/* Change notice and Signatory toggle */}
                    <div className="flex flex-wrap items-center gap-3 mt-1">
                      {isChanged && (
                        <span className="text-[11px] font-semibold text-amber-700 bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                          Changed from {req.position}
                        </span>
                      )}

                      <div className="flex items-center gap-1.5 text-xs">
                        <label
                          className={`inline-flex items-center gap-1.5 ${
                            !isSignatoryEligible
                              ? 'opacity-50 cursor-not-allowed text-slate-400'
                              : 'cursor-pointer text-slate-700'
                          }`}
                        >
                          <input
                            type="checkbox"
                            disabled={!isSignatoryEligible}
                            checked={Boolean(selectedSignatories[req.id]) && isSignatoryEligible}
                            onChange={(e) =>
                              setSelectedSignatories({
                                ...selectedSignatories,
                                [req.id]: e.target.checked,
                              })
                            }
                            className="rounded border-slate-300 text-brand-700 focus:ring-brand-700 h-3.5 w-3.5"
                          />
                          <span className="font-medium">Signatory</span>
                        </label>
                        {!isSignatoryEligible && (
                          <span className="text-[11px] text-slate-400 italic">
                            (Position cannot sign documents)
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* History / Reviewed Section */}
      {pastRequests.length > 0 && (
        <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
          <h2 className="text-sm font-bold text-slate-700 mb-4">Request History</h2>
          <div className="divide-y divide-slate-100">
            {pastRequests.map((req) => (
              <div key={req.id} className="py-3 flex items-center justify-between text-xs">
                <div>
                  <span className="font-semibold text-slate-800">{req.user_name || req.user_email}</span>
                  <span className="text-slate-400 mx-2">•</span>
                  <span className="text-slate-500">{req.position}</span>
                </div>
                <div className="flex items-center gap-3">
                  <span
                    className={`px-2 py-0.5 rounded text-xs font-semibold ${
                      req.status === 'approved'
                        ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                        : req.status === 'cancelled'
                        ? 'bg-slate-100 text-slate-600 border border-slate-200'
                        : 'bg-red-50 text-red-700 border border-red-200'
                    }`}
                  >
                    {req.status}
                  </span>
                  <span className="text-slate-400 text-xs">
                    {req.reviewed_at ? new Date(req.reviewed_at).toLocaleDateString() : ''}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
