import React, { useState, useEffect } from 'react';
import { ClubPermissions, Venue, NumberingSeries, Letterhead, Asset } from '../types';
import { api } from '../api/client';
import {
  Building,
  Hash,
  FileSpreadsheet,
  Plus,
  Edit2,
  Trash2,
  Upload,
  CheckCircle2,
  AlertCircle,
  Shield,
  Eye,
  Info,
  Layers,
  MapPin,
} from 'lucide-react';

interface AdminTabProps {
  clubId: string | number;
  permissions: ClubPermissions | null;
  members?: any[];
  onRefreshMembers?: () => void;
}

export const AdminTab: React.FC<AdminTabProps> = ({ clubId, permissions }) => {
  const [subTab, setSubTab] = useState<'venues' | 'numbering' | 'letterheads'>('venues');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Venues state
  const [venues, setVenues] = useState<Venue[]>([]);
  const [venueForm, setVenueForm] = useState<{
    id?: string;
    name: string;
    location: string;
    capacity: number | '';
    addressee: string;
    tech_assistant: string;
    faculty_in_charge: string;
  } | null>(null);

  // Numbering series state
  const [seriesList, setSeriesList] = useState<NumberingSeries[]>([]);
  const [seriesForm, setSeriesForm] = useState<NumberingSeries | null>(null);

  // Letterheads state
  const [letterheads, setLetterheads] = useState<Letterhead[]>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const [previewLetterhead, setPreviewLetterhead] = useState<Letterhead | null>(null);

  const isAdmin = permissions?.can_edit_settings || permissions?.role === 'admin' || permissions?.role === 'owner' || permissions?.is_platform_admin;

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      if (subTab === 'venues') {
        const data = await api.clubs.getVenues(clubId);
        setVenues(data);
      } else if (subTab === 'numbering') {
        const data = await api.clubs.getNumberingSeries(clubId);
        setSeriesList(data);
      } else if (subTab === 'letterheads') {
        const [lhs, asts] = await Promise.all([
          api.clubs.getLetterheads(clubId),
          api.clubs.getAssets(clubId),
        ]);
        setLetterheads(lhs);
        setAssets(asts);
        if (lhs.length > 0 && !previewLetterhead) {
          setPreviewLetterhead(lhs[0]);
        }
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load configuration');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [clubId, subTab]);

  // Venue actions
  const handleOpenAddVenue = () => {
    setVenueForm({ name: '', location: '', capacity: '', addressee: 'Dean (Student Welfare)', tech_assistant: '', faculty_in_charge: '' });
  };

  const handleOpenEditVenue = (v: Venue) => {
    setVenueForm({ id: v.id, name: v.name, location: v.location || '', capacity: v.capacity ?? '', addressee: v.addressee || '', tech_assistant: v.tech_assistant || '', faculty_in_charge: v.faculty_in_charge || '' });
  };

  const handleSaveVenue = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!venueForm) return;
    setError(null);
    try {
      const payload: Partial<Venue> = {
        name: venueForm.name.trim(),
        location: venueForm.location.trim() || undefined,
        capacity: venueForm.capacity !== '' ? Number(venueForm.capacity) : undefined,
        addressee: venueForm.addressee.trim() || undefined,
        tech_assistant: venueForm.tech_assistant.trim() || undefined,
        faculty_in_charge: venueForm.faculty_in_charge.trim() || undefined,
      };
      if (venueForm.id) {
        await api.clubs.updateVenue(clubId, venueForm.id, payload);
        setSuccess('Venue updated successfully.');
      } else {
        await api.clubs.createVenue(clubId, payload);
        setSuccess('Venue created successfully.');
      }
      setVenueForm(null);
      loadData();
    } catch (err: any) {
      setError(err.message || 'Failed to save venue');
    }
  };

  const handleDeleteVenue = async (v: Venue) => {
    if (!confirm(`Delete venue "${v.name}"?`)) return;
    setError(null);
    try {
      await api.clubs.deleteVenue(clubId, v.id);
      setSuccess(`Venue "${v.name}" deleted.`);
      loadData();
    } catch (err: any) {
      setError(err.message || 'Failed to delete venue');
    }
  };

  const handleSaveSeries = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!seriesForm) return;
    setError(null);
    try {
      await api.clubs.updateNumberingSeries(clubId, seriesForm.series_key, {
        format: seriesForm.format.trim(),
        academic_year: seriesForm.academic_year?.trim() || undefined,
        description: seriesForm.description?.trim() || undefined,
      });
      setSuccess(`Series "${seriesForm.series_key}" updated.`);
      setSeriesForm(null);
      loadData();
    } catch (err: any) {
      setError(err.message || 'Failed to update numbering series');
    }
  };

  // Logo upload
  const handleLogoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadingLogo(true);
    setError(null);
    try {
      const res = await api.clubs.uploadLogo(clubId, file);
      setSuccess(`Logo uploaded and normalized (${res.filename}).`);
      loadData();
    } catch (err: any) {
      setError(err.message || 'Failed to upload logo');
    } finally {
      setUploadingLogo(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4 sm:p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <Building className="w-6 h-6 text-[#1b365d]" />
            <h2 className="text-lg sm:text-xl font-bold text-slate-900">Club Administration & Configuration</h2>
          </div>
          <p className="mt-1 text-xs text-slate-500">
            Permission-checked settings for institutional venues, numbering series, and normalized letterheads.
          </p>
        </div>

        <div className="flex items-center gap-2 text-xs">
          {isAdmin ? (
            <span className="inline-flex items-center gap-1.5 bg-emerald-50 text-emerald-800 border border-emerald-300 font-semibold px-2.5 py-1 rounded-lg">
              <Shield className="w-3.5 h-3.5" /> Admin Access (Full CRUD)
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 bg-slate-100 text-slate-600 border border-slate-200 font-medium px-2.5 py-1 rounded-lg">
              <Eye className="w-3.5 h-3.5" /> Editor View (Read Only)
            </span>
          )}
        </div>
      </div>

      {/* Sub-tab Navigation */}
      <div className="flex border-b border-slate-200 bg-white rounded-t-xl px-4 pt-2 gap-2 overflow-x-auto no-scrollbar">
        {[
          { id: 'venues', label: 'Venues & Facilities', icon: MapPin },
          { id: 'letterheads', label: 'Letterheads & Logos', icon: FileSpreadsheet },
          { id: 'numbering', label: 'Numbering Series', icon: Hash },
        ].map((t) => {
          const Icon = t.icon;
          const active = subTab === t.id;
          return (
            <button
              key={t.id}
              onClick={() => {
                setSubTab(t.id as any);
                setError(null);
                setSuccess(null);
              }}
              className={`flex items-center gap-2 px-4 py-2.5 text-xs sm:text-sm font-semibold border-b-2 transition-colors whitespace-nowrap ${
                active
                  ? 'border-[#1b365d] text-[#1b365d] bg-slate-50/60 rounded-t-md'
                  : 'border-transparent text-slate-600 hover:text-slate-900 hover:bg-slate-50'
              }`}
            >
              <Icon className="w-4 h-4" />
              <span>{t.label}</span>
            </button>
          );
        })}
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

      {/* TAB 1: VENUES */}
      {subTab === 'venues' && (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden p-4 sm:p-6 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h3 className="text-sm sm:text-base font-bold text-slate-900">Campus Venues & Permission Addressees</h3>
              <p className="text-xs text-slate-500">
                Official venues prefill permission letters, addressees, tech assistants, and faculty in-charge.
              </p>
            </div>
            {isAdmin && (
              <button
                type="button"
                onClick={handleOpenAddVenue}
                className="inline-flex items-center justify-center gap-1.5 bg-[#1b365d] hover:bg-[#162a4a] text-white text-xs font-semibold px-3 py-2 rounded-lg transition-colors shadow-sm"
              >
                <Plus className="w-4 h-4" />
                Add Venue
              </button>
            )}
          </div>

          {loading ? (
            <div className="text-center py-8 text-xs text-slate-400">Loading venues...</div>
          ) : venues.length === 0 ? (
            <div className="text-center py-8 text-xs text-slate-500 bg-slate-50 rounded-lg border border-dashed border-slate-200">
              No venues configured for this club yet.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {venues.map((v) => (
                <div key={v.id} className="border border-slate-200 rounded-xl p-4 bg-slate-50/50 flex flex-col justify-between space-y-3">
                  <div>
                    <div className="flex items-start justify-between">
                      <div className="font-bold text-sm text-slate-900">{v.name}</div>
                      {v.capacity && (
                        <span className="text-[10px] bg-slate-200 text-slate-700 px-2 py-0.5 rounded font-mono font-semibold">
                          Cap: {v.capacity}
                        </span>
                      )}
                    </div>
                    {v.location && <div className="text-xs text-slate-500 mt-0.5">{v.location}</div>}

                    <div className="mt-3 pt-3 border-t border-slate-200/80 space-y-1 text-xs text-slate-700">
                      <div>
                        <span className="text-slate-400 font-medium">Addressee:</span>{' '}
                        <span className="font-semibold">{v.addressee || 'Associate Dean (SW)'}</span>
                      </div>
                      {v.tech_assistant && (
                        <div>
                          <span className="text-slate-400 font-medium">Tech Assistant:</span> {v.tech_assistant}
                        </div>
                      )}
                      {v.faculty_in_charge && (
                        <div>
                          <span className="text-slate-400 font-medium">Faculty In-Charge:</span> {v.faculty_in_charge}
                        </div>
                      )}
                    </div>
                  </div>

                  {isAdmin && (
                    <div className="pt-2 border-t border-slate-200 flex items-center justify-end gap-2 text-xs">
                      <button
                        type="button"
                        onClick={() => handleOpenEditVenue(v)}
                        className="inline-flex items-center gap-1 text-[#1b365d] hover:bg-blue-50 px-2 py-1 rounded font-semibold transition-colors"
                      >
                        <Edit2 className="w-3.5 h-3.5" /> Edit
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDeleteVenue(v)}
                        className="inline-flex items-center gap-1 text-red-600 hover:bg-red-50 px-2 py-1 rounded font-semibold transition-colors"
                      >
                        <Trash2 className="w-3.5 h-3.5" /> Delete
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB 2: NUMBERING SERIES */}
      {subTab === 'numbering' && (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden p-4 sm:p-6 space-y-4">
          <div>
            <h3 className="text-sm sm:text-base font-bold text-slate-900">Official Club Numbering Series & Counters</h3>
            <p className="text-xs text-slate-500 mt-1">
              Numbering series generate atomic, strictly unique document dispatch numbers. Counters increment monotonically.
            </p>
          </div>

          <div className="bg-amber-50 border border-amber-200 p-3.5 rounded-xl flex items-start gap-2.5 text-xs text-amber-900">
            <Info className="w-4 h-4 text-amber-700 flex-shrink-0 mt-0.5" />
            <div>
              <span className="font-bold">Institutional Immutability Guarantee:</span> Updating a series format applies only to future allocations. Existing generated documents permanently preserve their historically assigned reference numbers.
            </div>
          </div>

          {loading ? (
            <div className="text-center py-8 text-xs text-slate-400">Loading series...</div>
          ) : seriesList.length === 0 ? (
            <div className="text-center py-8 text-xs text-slate-500 bg-slate-50 rounded-lg border border-dashed border-slate-200">
              No numbering series found.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {seriesList.map((s) => (
                <div key={s.id} className="border border-slate-200 rounded-xl p-4 bg-slate-50/50 flex flex-col justify-between space-y-3">
                  <div>
                    <div className="flex items-center justify-between">
                      <span className="font-mono font-bold text-sm bg-blue-50 text-[#1b365d] px-2.5 py-1 rounded border border-blue-200">
                        {s.series_key}
                      </span>
                      <span className="text-xs font-mono font-semibold text-slate-600 bg-slate-100 px-2 py-0.5 rounded">
                        AY: {s.academic_year}
                      </span>
                    </div>

                    <div className="mt-3 space-y-1.5 text-xs">
                      <div>
                        <span className="text-slate-500 font-medium">Format Pattern:</span>
                        <div className="font-mono text-[11px] bg-white p-1.5 rounded border border-slate-200 mt-0.5 text-slate-800 break-all">
                          {s.format}
                        </div>
                      </div>

                      <div className="flex items-center justify-between pt-1">
                        <span className="text-slate-500 font-medium">Current Counter:</span>
                        <span className="font-mono font-bold text-slate-900 bg-emerald-50 text-emerald-800 px-2 py-0.5 rounded border border-emerald-200">
                          {s.current_counter}
                        </span>
                      </div>

                      {s.description && (
                        <div className="text-slate-600 text-[11px] pt-1">
                          {s.description}
                        </div>
                      )}
                    </div>
                  </div>

                  {isAdmin && (
                    <div className="pt-2 border-t border-slate-200 flex items-center justify-end text-xs">
                      <button
                        type="button"
                        onClick={() => setSeriesForm(s)}
                        className="inline-flex items-center gap-1 text-[#1b365d] hover:bg-blue-50 px-2 py-1 rounded font-semibold transition-colors"
                      >
                        <Edit2 className="w-3.5 h-3.5" /> Edit Format
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB 3: LETTERHEADS & LOGOS */}
      {subTab === 'letterheads' && (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden p-4 sm:p-6 space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h3 className="text-sm sm:text-base font-bold text-slate-900">Letterheads & Institutional Logos</h3>
              <p className="text-xs text-slate-500">
                Manage club official letterheads, logo normalization (RGBA to clean white canvas), and typography.
              </p>
            </div>

            {isAdmin && (
              <label className="inline-flex items-center justify-center gap-1.5 bg-[#1b365d] hover:bg-[#162a4a] text-white text-xs font-semibold px-3 py-2 rounded-lg cursor-pointer transition-colors shadow-sm">
                <Upload className="w-4 h-4" />
                <span>{uploadingLogo ? 'Normalizing...' : 'Upload Club Logo'}</span>
                <input
                  type="file"
                  accept="image/png,image/jpeg"
                  onChange={handleLogoUpload}
                  disabled={uploadingLogo}
                  className="hidden"
                />
              </label>
            )}
          </div>

          {/* Letterhead Preview */}
          <div className="border-2 border-slate-200 rounded-xl p-4 sm:p-6 bg-slate-50 space-y-4">
            <div className="text-xs font-bold text-slate-700 uppercase tracking-wider flex items-center gap-1.5">
              <Layers className="w-4 h-4 text-[#1b365d]" />
              Official Letterhead Preview
            </div>

            <div className="bg-white border border-slate-300 rounded-lg p-6 shadow-sm max-w-2xl mx-auto space-y-4">
              {/* Header block with logos */}
              <div className="flex items-center justify-between border-b-2 border-[#1b365d] pb-4">
                <div className="h-16 w-16 flex items-center justify-center p-1 border border-slate-200 rounded bg-white">
                  <img src="/assets/svnit_crest.png" alt="SVNIT Crest" className="max-h-full max-w-full object-contain" />
                </div>

                <div className="text-center px-4 flex-1">
                  <h4 className="font-serif font-bold text-xs sm:text-sm text-slate-900 uppercase tracking-wide">
                    Sardar Vallabhbhai National Institute of Technology, Surat
                  </h4>
                  <p className="text-[11px] font-bold text-[#1b365d] uppercase tracking-wider mt-0.5">
                    {previewLetterhead?.title_text || 'Student Chapter'}
                  </p>
                  <p className="text-[10px] text-slate-500 italic mt-0.5">
                    Ichchhanath, Surat - 395007, Gujarat, India
                  </p>
                </div>

                <div className="h-16 w-16 flex items-center justify-center p-1 border border-slate-200 rounded bg-white">
                  <img
                    src={`/api/v1/clubs/${clubId}/logo`}
                    alt="Club Logo"
                    className="max-h-full max-w-full object-contain"
                    onError={(e) => {
                      (e.target as HTMLElement).style.display = 'none';
                    }}
                  />
                </div>
              </div>

              {/* Sample Document Body Placeholder */}
              <div className="py-6 space-y-2 text-center text-slate-400 text-xs">
                <p className="italic">Official dispatch document content renders here.</p>
                <div className="h-2 bg-slate-100 rounded w-3/4 mx-auto"></div>
                <div className="h-2 bg-slate-100 rounded w-1/2 mx-auto"></div>
              </div>

              {/* Footer */}
              <div className="border-t border-slate-200 pt-3 text-center text-[10px] text-slate-500">
                {previewLetterhead?.subtitle_text || 'Website: www.svnit.ac.in | Official Student Portal'}
              </div>
            </div>
          </div>

          {/* Letterheads and Assets List */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="border border-slate-200 rounded-xl p-4 bg-slate-50/50 space-y-3">
              <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
                Configured Letterheads ({letterheads.length})
              </h4>
              <div className="space-y-2 text-xs">
                {letterheads.map((lh) => (
                  <div
                    key={lh.id}
                    onClick={() => setPreviewLetterhead(lh)}
                    className={`p-3 rounded-lg border cursor-pointer transition-colors ${
                      previewLetterhead?.id === lh.id
                        ? 'bg-blue-50 border-[#1b365d] text-[#1b365d]'
                        : 'bg-white border-slate-200 hover:border-slate-300'
                    }`}
                  >
                    <div className="font-bold flex items-center justify-between">
                      <span>{lh.name}</span>
                      {lh.is_default && (
                        <span className="text-[10px] bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded font-semibold">
                          Default
                        </span>
                      )}
                    </div>
                    <div className="text-[11px] text-slate-500 mt-1">{lh.title_text}</div>
                  </div>
                ))}
              </div>
            </div>

            <div className="border border-slate-200 rounded-xl p-4 bg-slate-50/50 space-y-3">
              <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
                Club Logo Assets ({assets.length})
              </h4>
              <div className="space-y-2 text-xs">
                {assets.map((ast) => (
                  <div key={ast.id} className="p-3 bg-white rounded-lg border border-slate-200 flex items-center justify-between">
                    <div>
                      <div className="font-semibold text-slate-900">{ast.filename}</div>
                      <div className="text-[10px] text-slate-400 font-mono mt-0.5">{ast.mime} • {ast.size ? `${Math.round(ast.size / 1024)} KB` : 'Normalized'}</div>
                    </div>
                    <span className="text-[10px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded font-mono">
                      {ast.kind}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* VENUE MODAL */}
      {venueForm && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6 space-y-4">
            <h3 className="font-bold text-base text-slate-900">
              {venueForm.id ? 'Edit Campus Venue' : 'Add Campus Venue'}
            </h3>
            <form onSubmit={handleSaveVenue} className="space-y-3 text-xs">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">Venue Name *</label>
                <input
                  type="text"
                  required
                  value={venueForm.name}
                  onChange={(e) => setVenueForm({ ...venueForm, name: e.target.value })}
                  placeholder="e.g. Seminar Hall, Department of Computer Engineering"
                  className="w-full border border-slate-300 rounded-lg p-2.5"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Location / Building</label>
                  <input
                    type="text"
                    value={venueForm.location}
                    onChange={(e) => setVenueForm({ ...venueForm, location: e.target.value })}
                    placeholder="e.g. DoCSE 1st Floor"
                    className="w-full border border-slate-300 rounded-lg p-2.5"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Capacity</label>
                  <input
                    type="number"
                    value={venueForm.capacity}
                    onChange={(e) => setVenueForm({ ...venueForm, capacity: e.target.value ? Number(e.target.value) : '' })}
                    placeholder="e.g. 150"
                    className="w-full border border-slate-300 rounded-lg p-2.5"
                  />
                </div>
              </div>
              <div>
                <label className="block font-semibold text-slate-700 mb-1">Letter Addressee</label>
                <input
                  type="text"
                  value={venueForm.addressee}
                  onChange={(e) => setVenueForm({ ...venueForm, addressee: e.target.value })}
                  placeholder="e.g. Head of Department / Associate Dean (SW)"
                  className="w-full border border-slate-300 rounded-lg p-2.5"
                />
              </div>
              <div>
                <label className="block font-semibold text-slate-700 mb-1">Technical Assistant</label>
                <input
                  type="text"
                  value={venueForm.tech_assistant}
                  onChange={(e) => setVenueForm({ ...venueForm, tech_assistant: e.target.value })}
                  placeholder="e.g. Shri R. K. Patel"
                  className="w-full border border-slate-300 rounded-lg p-2.5"
                />
              </div>
              <div>
                <label className="block font-semibold text-slate-700 mb-1">Faculty In-Charge</label>
                <input
                  type="text"
                  value={venueForm.faculty_in_charge}
                  onChange={(e) => setVenueForm({ ...venueForm, faculty_in_charge: e.target.value })}
                  placeholder="e.g. Dr. P. M. Shah"
                  className="w-full border border-slate-300 rounded-lg p-2.5"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2 border-t border-slate-200">
                <button
                  type="button"
                  onClick={() => setVenueForm(null)}
                  className="px-3 py-2 text-slate-600 hover:bg-slate-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-[#1b365d] hover:bg-[#162a4a] text-white font-semibold rounded-lg shadow-sm"
                >
                  Save Venue
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* NUMBERING MODAL */}
      {seriesForm && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6 space-y-4">
            <h3 className="font-bold text-base text-slate-900">
              Edit Numbering Series: {seriesForm.series_key}
            </h3>
            <p className="text-xs text-amber-800 bg-amber-50 p-2.5 rounded-lg border border-amber-200">
              Format changes apply only to future documents; historical documents preserve allocated numbers.
            </p>
            <form onSubmit={handleSaveSeries} className="space-y-3 text-xs">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">Format Template *</label>
                <input
                  type="text"
                  required
                  value={seriesForm.format}
                  onChange={(e) => setSeriesForm({ ...seriesForm, format: e.target.value })}
                  placeholder="{club}/{yy}-{next}/{series}/{seq:03d}"
                  className="w-full border border-slate-300 rounded-lg p-2.5 font-mono text-xs"
                />
              </div>
              <div>
                <label className="block font-semibold text-slate-700 mb-1">Academic Year</label>
                <input
                  type="text"
                  value={seriesForm.academic_year || ''}
                  onChange={(e) => setSeriesForm({ ...seriesForm, academic_year: e.target.value })}
                  placeholder="2026-27"
                  className="w-full border border-slate-300 rounded-lg p-2.5"
                />
              </div>
              <div>
                <label className="block font-semibold text-slate-700 mb-1">Description</label>
                <textarea
                  rows={2}
                  value={seriesForm.description || ''}
                  onChange={(e) => setSeriesForm({ ...seriesForm, description: e.target.value })}
                  placeholder="Purpose of this numbering series..."
                  className="w-full border border-slate-300 rounded-lg p-2.5"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2 border-t border-slate-200">
                <button
                  type="button"
                  onClick={() => setSeriesForm(null)}
                  className="px-3 py-2 text-slate-600 hover:bg-slate-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-[#1b365d] hover:bg-[#162a4a] text-white font-semibold rounded-lg shadow-sm"
                >
                  Save Format
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
