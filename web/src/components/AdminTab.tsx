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
  HardDrive,
  RefreshCw,
} from 'lucide-react';

interface AdminTabProps {
  clubId: string | number;
  permissions: ClubPermissions | null;
  members?: any[];
  onRefreshMembers?: () => void;
}

const DEFAULT_APPROVAL_CHAIN = [
  { name: '', designation: 'Chairman, F& SW' },
  { name: '', designation: 'Associate Dean(SW)' },
  { name: '', designation: 'Dean (Students Welfare)' },
];

function parseApprovalChain(raw: unknown): { name: string; designation: string }[] {
  const entries = Array.isArray(raw) ? raw : [];
  return DEFAULT_APPROVAL_CHAIN.map((fallback, i) => {
    const value = entries[i];
    if (typeof value !== 'string') return { ...fallback };
    const [name, ...rest] = value.split('\n');
    return { name: (name || '').trim(), designation: rest.join(' ').trim() || fallback.designation };
  });
}

export const AdminTab: React.FC<AdminTabProps> = ({ clubId, permissions, onRefreshMembers }) => {
  const [subTab, setSubTab] = useState<'general' | 'venues' | 'numbering' | 'letterheads' | 'storage'>('general');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [storageStats, setStorageStats] = useState<any>(null);
  const [cleaning, setCleaning] = useState(false);
  const [logoVersion, setLogoVersion] = useState(Date.now());

  // General Settings state
  const [clubProfile, setClubProfile] = useState<{
    name: string;
    short_name: string;
    slug: string;
    chapter_code: string;
    head_of_account: string;
    department: string;
    department_short: string;
    brand_color: string;
    footer_text: string;
    approval_chain: { name: string; designation: string }[];
    academic_year_default: string;
    default_mode: string;
    default_purchase_order: string;
    default_advance: string;
    default_lab_office: string;
  }>({
    name: '',
    short_name: '',
    slug: '',
    chapter_code: '',
    head_of_account: '',
    department: '',
    department_short: '',
    brand_color: '#1b365d',
    footer_text: '',
    approval_chain: DEFAULT_APPROVAL_CHAIN.map((a) => ({ ...a })),
    academic_year_default: '2026-27',
    default_mode: 'Offline',
    default_purchase_order: 'NiL',
    default_advance: 'NiL',
    default_lab_office: 'Student Council',
  });
  const [savingGeneral, setSavingGeneral] = useState(false);

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
      if (subTab === 'general') {
        const club = await api.clubs.get(clubId);
        const settings = club.settings || {};
        const defaults = settings.defaults || {};
        setClubProfile({
          name: club.name || '',
          short_name: club.short_name || club.code || '',
          slug: club.slug || '',
          chapter_code: club.chapter_code || '',
          head_of_account: club.head_of_account || '',
          department: club.department || settings.department || '',
          department_short: settings.department_short || '',
          brand_color: settings.brand_color || '#1b365d',
          footer_text: settings.footer_text || '',
          approval_chain: parseApprovalChain(settings.approval_chain),
          academic_year_default: club.academic_year_default || club.academic_year || settings.academic_year || '2026-27',
          default_mode: defaults.mode || 'Offline',
          default_purchase_order: defaults.purchase_order || 'NiL',
          default_advance: defaults.advance || 'NiL',
          default_lab_office: defaults.lab_office || defaults.office_lab || 'Student Council',
        });
      } else if (subTab === 'venues') {
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
      } else if (subTab === 'storage') {
        const stats = await api.clubs.getStorageStats(clubId);
        setStorageStats(stats);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load configuration');
    } finally {
      setLoading(false);
    }
  };

  const handleSaveGeneral = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isAdmin) return;
    setError(null);
    setSuccess(null);
    setSavingGeneral(true);
    try {
      const payload = {
        name: clubProfile.name.trim(),
        short_name: clubProfile.short_name.trim(),
        chapter_code: clubProfile.chapter_code.trim() || undefined,
        head_of_account: clubProfile.head_of_account.trim() || undefined,
        academic_year_default: clubProfile.academic_year_default.trim(),
        department: clubProfile.department.trim(),
        settings: {
          department: clubProfile.department.trim(),
          department_short: clubProfile.department_short.trim(),
          brand_color: clubProfile.brand_color,
          footer_text: clubProfile.footer_text.trim(),
          // Stored as "Name\nDesignation" in signing order (read by the approval note).
          approval_chain: clubProfile.approval_chain.map((a) => `${a.name.trim()}\n${a.designation.trim()}`),
          academic_year: clubProfile.academic_year_default.trim(),
          defaults: {
            mode: clubProfile.default_mode,
            purchase_order: clubProfile.default_purchase_order.trim(),
            advance: clubProfile.default_advance.trim(),
            lab_office: clubProfile.default_lab_office.trim(),
          },
        },
      };
      await api.clubs.update(clubId, payload);
      setSuccess('Club settings and standing defaults saved successfully.');
      onRefreshMembers?.();
    } catch (err: any) {
      setError(err.message || 'Failed to save club settings');
    } finally {
      setSavingGeneral(false);
    }
  };

  const handleCleanStorage = async () => {
    setCleaning(true);
    setError(null);
    setSuccess(null);
    try {
      const res = await api.clubs.runStorageGc(clubId);
      setSuccess(res.message || 'Storage cleanup completed successfully.');
      const stats = await api.clubs.getStorageStats(clubId);
      setStorageStats(stats);
    } catch (err: any) {
      setError(err.message || 'Failed to clean storage.');
    } finally {
      setCleaning(false);
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
    setVenueForm({
      id: v.id,
      name: v.name,
      location: v.location || v.short_name || '',
      capacity: v.capacity ?? '',
      addressee: v.addressee || v.addressee_default || '',
      tech_assistant: v.tech_assistant || (v as any).tech_assistant_name || '',
      faculty_in_charge: v.faculty_in_charge || (v as any).faculty_incharge_name || '',
    });
  };

  const handleSaveVenue = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!venueForm) return;
    setError(null);
    try {
      const payload: any = {
        name: venueForm.name.trim(),
        short_name: venueForm.location.trim() || undefined,
        location: venueForm.location.trim() || undefined,
        capacity: venueForm.capacity !== '' ? Number(venueForm.capacity) : undefined,
        addressee_default: venueForm.addressee.trim() || undefined,
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
      const seriesKey = seriesForm.series_key || (seriesForm as any).key;
      if (!seriesKey) {
        throw new Error('Series key is missing');
      }
      await api.clubs.updateNumberingSeries(clubId, seriesKey, {
        format: seriesForm.format.trim(),
        academic_year: seriesForm.academic_year?.trim() || undefined,
        description: seriesForm.description?.trim() || undefined,
      });
      setSuccess(`Series "${seriesKey}" updated.`);
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
      setLogoVersion(Date.now());
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
            <Building className="w-6 h-6 text-brand-700" />
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
          { id: 'general', label: 'General & Profile', icon: Building },
          { id: 'venues', label: 'Venues & Facilities', icon: MapPin },
          { id: 'letterheads', label: 'Letterheads & Logos', icon: FileSpreadsheet },
          { id: 'numbering', label: 'Numbering Series', icon: Hash },
          { id: 'storage', label: 'Storage & Retention', icon: HardDrive },
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
                  ? 'border-brand-700 text-brand-700 bg-slate-50/60 rounded-t-md'
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

      {/* TAB 0: GENERAL & PROFILE */}
      {subTab === 'general' && (
        <form onSubmit={handleSaveGeneral} className="space-y-6">
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden p-4 sm:p-6 space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-slate-200">
              <div>
                <h3 className="text-sm sm:text-base font-bold text-slate-900 flex items-center gap-2">
                  <Building className="w-5 h-5 text-brand-700" /> Club Profile & Institutional Settings
                </h3>
                <p className="text-xs text-slate-500 mt-1">
                  Core club identification, chapter details, institutional head of account, and default academic year.
                </p>
              </div>

              {isAdmin && (
                <button
                  type="submit"
                  disabled={savingGeneral}
                  className="inline-flex items-center gap-2 px-4 py-2 bg-brand-700 hover:bg-[#162a4a] disabled:opacity-50 text-white text-xs sm:text-sm font-semibold rounded-lg shadow-sm transition-colors"
                >
                  {savingGeneral ? (
                    <>
                      <RefreshCw className="w-4 h-4 animate-spin" /> Saving...
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="w-4 h-4" /> Save Settings
                    </>
                  )}
                </button>
              )}
            </div>

            {/* Club Identity Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 text-xs">
              <div className="lg:col-span-2">
                <label className="block font-semibold text-slate-700 mb-1">Club Full Name *</label>
                <input
                  type="text"
                  required
                  disabled={!isAdmin}
                  value={clubProfile.name}
                  onChange={(e) => setClubProfile({ ...clubProfile, name: e.target.value })}
                  placeholder="e.g. Google Developer Student Clubs"
                  className="w-full border border-slate-300 rounded-lg p-2.5 disabled:bg-slate-50 disabled:text-slate-500"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Short Name / Code *</label>
                <input
                  type="text"
                  required
                  disabled={!isAdmin}
                  value={clubProfile.short_name}
                  onChange={(e) => setClubProfile({ ...clubProfile, short_name: e.target.value })}
                  placeholder="e.g. GDSC"
                  className="w-full border border-slate-300 rounded-lg p-2.5 font-bold disabled:bg-slate-50 disabled:text-slate-500"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Club URL Slug</label>
                <input
                  type="text"
                  disabled
                  value={clubProfile.slug}
                  className="w-full border border-slate-200 bg-slate-100 rounded-lg p-2.5 font-mono text-slate-600"
                />
                <span className="text-xs text-slate-400 mt-0.5 block">Unique system identifier for document numbering.</span>
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Chapter Code</label>
                <input
                  type="text"
                  disabled={!isAdmin}
                  value={clubProfile.chapter_code}
                  onChange={(e) => setClubProfile({ ...clubProfile, chapter_code: e.target.value })}
                  placeholder="e.g. SVNIT-GDSC"
                  className="w-full border border-slate-300 rounded-lg p-2.5 disabled:bg-slate-50 disabled:text-slate-500 font-mono"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Academic Department</label>
                <input
                  type="text"
                  disabled={!isAdmin}
                  value={clubProfile.department}
                  onChange={(e) => setClubProfile({ ...clubProfile, department: e.target.value })}
                  placeholder="e.g. Computer Science & Engineering"
                  className="w-full border border-slate-300 rounded-lg p-2.5 disabled:bg-slate-50 disabled:text-slate-500"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Department Short Name</label>
                <input
                  type="text"
                  disabled={!isAdmin}
                  value={clubProfile.department_short}
                  onChange={(e) => setClubProfile({ ...clubProfile, department_short: e.target.value })}
                  placeholder="e.g. CSE"
                  className="w-full border border-slate-300 rounded-lg p-2.5 disabled:bg-slate-50 disabled:text-slate-500"
                />
                <p className="text-xs text-slate-500 mt-1">Printed in lines such as &quot;Signature of HoD (CSE)&quot;.</p>
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1" htmlFor="brand-color">Letterhead colour</label>
                <div className="flex items-center gap-2">
                  <input
                    id="brand-color"
                    type="color"
                    disabled={!isAdmin}
                    value={clubProfile.brand_color}
                    onChange={(e) => setClubProfile({ ...clubProfile, brand_color: e.target.value })}
                    className="h-10 w-12 border border-slate-300 rounded-lg p-1 bg-white disabled:opacity-60"
                  />
                  <input
                    type="text"
                    disabled={!isAdmin}
                    value={clubProfile.brand_color}
                    onChange={(e) => setClubProfile({ ...clubProfile, brand_color: e.target.value })}
                    pattern="#[0-9a-fA-F]{6}"
                    aria-label="Letterhead colour hex code"
                    className="w-28 border border-slate-300 rounded-lg p-2.5 font-mono disabled:bg-slate-50 disabled:text-slate-500"
                  />
                </div>
                <p className="text-xs text-slate-500 mt-1">Used for the club name on the generated letterhead.</p>
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1" htmlFor="footer-text">Document footer</label>
                <input
                  id="footer-text"
                  type="text"
                  disabled={!isAdmin}
                  value={clubProfile.footer_text}
                  onChange={(e) => setClubProfile({ ...clubProfile, footer_text: e.target.value })}
                  placeholder="e.g. ACM Student Chapter · SVNIT Surat"
                  maxLength={120}
                  className="w-full border border-slate-300 rounded-lg p-2.5 disabled:bg-slate-50 disabled:text-slate-500"
                />
                <p className="text-xs text-slate-500 mt-1">Printed at the bottom of every page with the page number.</p>
              </div>

              <div className="md:col-span-2">
                <label className="block font-semibold text-slate-700 mb-1">Approval Signatories (Approval Note)</label>
                <p className="text-xs text-slate-500 mb-2">
                  Officials who sign the approval note, in order. Leave a name blank to print only the designation.
                </p>
                <div className="space-y-2">
                  {clubProfile.approval_chain.map((entry, idx) => (
                    <div key={idx} className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      <input
                        type="text"
                        disabled={!isAdmin}
                        value={entry.name}
                        aria-label={`Signatory ${idx + 1} name`}
                        onChange={(e) => {
                          const next = clubProfile.approval_chain.map((a, i) => (i === idx ? { ...a, name: e.target.value } : a));
                          setClubProfile({ ...clubProfile, approval_chain: next });
                        }}
                        placeholder="Name (e.g. Dr. A. B. Sharma)"
                        className="w-full border border-slate-300 rounded-lg p-2.5 disabled:bg-slate-50 disabled:text-slate-500"
                      />
                      <input
                        type="text"
                        disabled={!isAdmin}
                        value={entry.designation}
                        aria-label={`Signatory ${idx + 1} designation`}
                        onChange={(e) => {
                          const next = clubProfile.approval_chain.map((a, i) => (i === idx ? { ...a, designation: e.target.value } : a));
                          setClubProfile({ ...clubProfile, approval_chain: next });
                        }}
                        placeholder="Designation"
                        className="w-full border border-slate-300 rounded-lg p-2.5 disabled:bg-slate-50 disabled:text-slate-500"
                      />
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Head of Account</label>
                <input
                  type="text"
                  disabled={!isAdmin}
                  value={clubProfile.head_of_account}
                  onChange={(e) => setClubProfile({ ...clubProfile, head_of_account: e.target.value })}
                  placeholder="e.g. Student Welfare Account"
                  className="w-full border border-slate-300 rounded-lg p-2.5 disabled:bg-slate-50 disabled:text-slate-500"
                />
                <span className="text-xs text-slate-400 mt-0.5 block">Account credited/debited on budget approvals.</span>
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Default Academic Year *</label>
                <input
                  type="text"
                  required
                  disabled={!isAdmin}
                  value={clubProfile.academic_year_default}
                  onChange={(e) => setClubProfile({ ...clubProfile, academic_year_default: e.target.value })}
                  placeholder="e.g. 2026-27"
                  className="w-full border border-slate-300 rounded-lg p-2.5 font-bold disabled:bg-slate-50 disabled:text-slate-500"
                />
                <span className="text-xs text-slate-400 mt-0.5 block">Applied to newly drafted letters and series counters.</span>
              </div>
            </div>

            {/* Standing Defaults Section */}
            <div className="pt-6 border-t border-slate-200 space-y-4">
              <div>
                <h4 className="text-xs font-bold text-slate-900 flex items-center gap-1.5">
                  <Layers className="w-4 h-4 text-brand-700" /> Standing Form Defaults (Auto-fill)
                </h4>
                <p className="text-xs text-slate-500 mt-0.5">
                  Pre-configured defaults automatically populate event forms and financial document templates.
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 text-xs">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Default Event Mode</label>
                  <select
                    disabled={!isAdmin}
                    value={clubProfile.default_mode}
                    onChange={(e) => setClubProfile({ ...clubProfile, default_mode: e.target.value })}
                    className="w-full border border-slate-300 rounded-lg p-2.5 bg-white disabled:bg-slate-50 disabled:text-slate-500"
                  >
                    <option value="Offline">Offline (Campus)</option>
                    <option value="Online">Online (Virtual)</option>
                    <option value="Hybrid">Hybrid</option>
                  </select>
                </div>

                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Purchase Order Default</label>
                  <input
                    type="text"
                    disabled={!isAdmin}
                    value={clubProfile.default_purchase_order}
                    onChange={(e) => setClubProfile({ ...clubProfile, default_purchase_order: e.target.value })}
                    placeholder="e.g. NiL"
                    className="w-full border border-slate-300 rounded-lg p-2.5 disabled:bg-slate-50 disabled:text-slate-500 font-mono"
                  />
                  <span className="text-xs text-slate-400 mt-0.5 block">Bill certificate PO standing value.</span>
                </div>

                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Advance Amount Default</label>
                  <input
                    type="text"
                    disabled={!isAdmin}
                    value={clubProfile.default_advance}
                    onChange={(e) => setClubProfile({ ...clubProfile, default_advance: e.target.value })}
                    placeholder="e.g. NiL"
                    className="w-full border border-slate-300 rounded-lg p-2.5 disabled:bg-slate-50 disabled:text-slate-500 font-mono"
                  />
                  <span className="text-xs text-slate-400 mt-0.5 block">Bill certificate advance value.</span>
                </div>

                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Office / Laboratory Default</label>
                  <input
                    type="text"
                    disabled={!isAdmin}
                    value={clubProfile.default_lab_office}
                    onChange={(e) => setClubProfile({ ...clubProfile, default_lab_office: e.target.value })}
                    placeholder="e.g. Student Council"
                    className="w-full border border-slate-300 rounded-lg p-2.5 disabled:bg-slate-50 disabled:text-slate-500"
                  />
                  <span className="text-xs text-slate-400 mt-0.5 block">Default office or facility label.</span>
                </div>
              </div>
            </div>

            {/* Club Logo Quick Card */}
            <div className="pt-6 border-t border-slate-200 flex flex-col sm:flex-row items-center justify-between gap-4 bg-slate-50/70 p-4 rounded-xl border border-slate-200">
              <div className="flex items-center gap-4">
                <div className="h-16 w-16 bg-white border border-slate-200 rounded-xl p-1.5 flex items-center justify-center shadow-xs">
                  <img
                    src={`/api/v1/clubs/${clubId}/logo?v=${logoVersion}`}
                    alt="Club Logo"
                    className="max-h-full max-w-full object-contain"
                    onError={(e) => {
                      (e.target as HTMLElement).style.display = 'none';
                    }}
                  />
                  <Building className="w-6 h-6 text-slate-300" />
                </div>
                <div>
                  <h4 className="text-xs font-bold text-slate-900">Active Club Logo</h4>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Automatically centered and composited on official letterheads and templates.
                  </p>
                </div>
              </div>

              {isAdmin && (
                <label className="inline-flex items-center gap-1.5 bg-white border border-slate-300 hover:border-slate-400 text-slate-700 text-xs font-semibold px-3 py-2 rounded-lg cursor-pointer transition-colors shadow-2xs">
                  <Upload className="w-4 h-4 text-brand-700" />
                  <span>{uploadingLogo ? 'Uploading...' : 'Replace Logo'}</span>
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
          </div>
        </form>
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
                className="inline-flex items-center justify-center gap-1.5 bg-brand-700 hover:bg-[#162a4a] text-white text-xs font-semibold px-3 py-2 rounded-lg transition-colors shadow-sm"
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
                        <span className="text-xs bg-slate-200 text-slate-700 px-2 py-0.5 rounded font-mono font-semibold">
                          Cap: {v.capacity}
                        </span>
                      )}
                    </div>
                    {(v.location || v.short_name) && <div className="text-xs text-slate-500 mt-0.5">{v.location || v.short_name}</div>}

                    <div className="mt-3 pt-3 border-t border-slate-200/80 space-y-1 text-xs text-slate-700">
                      <div>
                        <span className="text-slate-400 font-medium">Addressee:</span>{' '}
                        <span className="font-semibold">{v.addressee || v.addressee_default || 'Associate Dean (SW)'}</span>
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
                        className="inline-flex items-center gap-1 text-brand-700 hover:bg-brand-50 px-2 py-1 rounded font-semibold transition-colors"
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
                      <span className="font-mono font-bold text-sm bg-brand-50 text-brand-700 px-2.5 py-1 rounded border border-brand-200">
                        {s.series_key || (s as any).key}
                      </span>
                      <span className="text-xs font-mono font-semibold text-slate-600 bg-slate-100 px-2 py-0.5 rounded">
                        AY: {s.academic_year}
                      </span>
                    </div>

                    <div className="mt-3 space-y-1.5 text-xs">
                      <div>
                        <span className="text-slate-500 font-medium">Format Pattern:</span>
                        <div className="font-mono text-xs bg-white p-1.5 rounded border border-slate-200 mt-0.5 text-slate-800 break-all">
                          {s.format}
                        </div>
                      </div>

                      <div className="flex items-center justify-between pt-1">
                        <span className="text-slate-500 font-medium">Current Counter:</span>
                        <span className="font-mono font-bold text-slate-900 bg-emerald-50 text-emerald-800 px-2 py-0.5 rounded border border-emerald-200">
                          {s.current_counter ?? (s as any).last_seq ?? 0}
                        </span>
                      </div>

                      {s.description && (
                        <div className="text-slate-600 text-xs pt-1">
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
                        className="inline-flex items-center gap-1 text-brand-700 hover:bg-brand-50 px-2 py-1 rounded font-semibold transition-colors"
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
              <label className="inline-flex items-center justify-center gap-1.5 bg-brand-700 hover:bg-[#162a4a] text-white text-xs font-semibold px-3 py-2 rounded-lg cursor-pointer transition-colors shadow-sm">
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
            <div className="text-xs font-bold text-slate-700 flex items-center gap-1.5">
              <Layers className="w-4 h-4 text-brand-700" />
              Official Letterhead Preview
            </div>

            <div className="bg-white border border-slate-300 rounded-lg p-6 shadow-sm max-w-2xl mx-auto space-y-4">
              {/* Header block with logos */}
              <div className="flex items-center justify-between border-b-2 border-brand-700 pb-4">
                <div className="h-16 w-16 flex items-center justify-center p-1 border border-slate-200 rounded bg-white">
                  <img src="/assets/svnit_crest.png" alt="SVNIT Crest" className="max-h-full max-w-full object-contain" />
                </div>

                <div className="text-center px-4 flex-1">
                  <h4 className="font-serif font-bold text-xs sm:text-sm text-slate-900">
                    Sardar Vallabhbhai National Institute of Technology, Surat
                  </h4>
                  <p className="text-xs font-bold text-brand-700 mt-0.5">
                    {previewLetterhead?.title_text || 'Student Chapter'}
                  </p>
                  <p className="text-xs text-slate-500 italic mt-0.5">
                    Ichchhanath, Surat - 395007, Gujarat, India
                  </p>
                </div>

                <div className="h-16 w-16 flex items-center justify-center p-1 border border-slate-200 rounded bg-white">
                  <img
                    src={`/api/v1/clubs/${clubId}/logo?v=${logoVersion}`}
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
              <div className="border-t border-slate-200 pt-3 text-center text-xs text-slate-500">
                {previewLetterhead?.subtitle_text || 'Website: www.svnit.ac.in | Official Student Portal'}
              </div>
            </div>
          </div>

          {/* Letterheads and Assets List */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="border border-slate-200 rounded-xl p-4 bg-slate-50/50 space-y-3">
              <h4 className="text-xs font-bold text-slate-800">
                Configured Letterheads ({letterheads.length})
              </h4>
              <div className="space-y-2 text-xs">
                {letterheads.map((lh) => (
                  <div
                    key={lh.id}
                    onClick={() => setPreviewLetterhead(lh)}
                    className={`p-3 rounded-lg border cursor-pointer transition-colors ${
                      previewLetterhead?.id === lh.id
                        ? 'bg-brand-50 border-brand-700 text-brand-700'
                        : 'bg-white border-slate-200 hover:border-slate-300'
                    }`}
                  >
                    <div className="font-bold flex items-center justify-between">
                      <span>{lh.name}</span>
                      {lh.is_default && (
                        <span className="text-xs bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded font-semibold">
                          Default
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-slate-500 mt-1">{lh.title_text}</div>
                  </div>
                ))}
              </div>
            </div>

            <div className="border border-slate-200 rounded-xl p-4 bg-slate-50/50 space-y-3">
              <h4 className="text-xs font-bold text-slate-800">
                Club Logo Assets ({assets.length})
              </h4>
              <div className="space-y-2 text-xs">
                {assets.map((ast) => (
                  <div key={ast.id} className="p-3 bg-white rounded-lg border border-slate-200 flex items-center justify-between">
                    <div>
                      <div className="font-semibold text-slate-900">{ast.filename}</div>
                      <div className="text-xs text-slate-400 font-mono mt-0.5">{ast.mime} • {ast.size ? `${Math.round(ast.size / 1024)} KB` : 'Normalized'}</div>
                    </div>
                    <span className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded font-mono">
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
                  className="px-4 py-2 bg-brand-700 hover:bg-[#162a4a] text-white font-semibold rounded-lg shadow-sm"
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
              Edit Numbering Series: {seriesForm.series_key || (seriesForm as any).key}
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
                  className="px-4 py-2 bg-brand-700 hover:bg-[#162a4a] text-white font-semibold rounded-lg shadow-sm"
                >
                  Save Format
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* TAB 4: STORAGE & RETENTION */}
      {subTab === 'storage' && (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden p-4 sm:p-6 space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200">
            <div>
              <h3 className="text-sm sm:text-base font-bold text-slate-900 flex items-center gap-2">
                <HardDrive className="w-5 h-5 text-brand-700" /> Club Storage & Retention
              </h3>
              <p className="text-xs text-slate-500 mt-1">
                Monitor storage consumption for documents, previews, and templates, and perform safe garbage collection.
              </p>
            </div>
            {isAdmin && (
              <button
                type="button"
                onClick={handleCleanStorage}
                disabled={cleaning}
                className="inline-flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white text-xs sm:text-sm font-semibold rounded-lg shadow-sm transition-colors"
              >
                <RefreshCw className={`w-4 h-4 ${cleaning ? 'animate-spin' : ''}`} />
                {cleaning ? 'Cleaning up...' : 'Clean up now'}
              </button>
            )}
          </div>

          {/* Usage Metrics */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-slate-50 border border-slate-200 rounded-xl p-4">
              <span className="text-xs font-semibold text-slate-500 block">Total Usage</span>
              <span className="text-2xl font-black text-slate-900 mt-1 block">
                {storageStats?.usage?.total_mb ?? 0} MB
              </span>
              <span className="text-xs text-slate-500 mt-1 block">
                {((storageStats?.usage?.total_bytes ?? 0) / 1024).toFixed(1)} KB total disk space
              </span>
            </div>

            <div className="bg-slate-50 border border-slate-200 rounded-xl p-4">
              <span className="text-xs font-semibold text-slate-500 block">Documents</span>
              <span className="text-2xl font-black text-slate-900 mt-1 block">
                {(((storageStats?.usage?.documents_bytes ?? 0) / (1024 * 1024))).toFixed(2)} MB
              </span>
              <span className="text-xs text-slate-500 mt-1 block">
                {storageStats?.usage?.documents_files ?? 0} physical files (DOCX + PDF)
              </span>
            </div>

            <div className="bg-slate-50 border border-slate-200 rounded-xl p-4">
              <span className="text-xs font-semibold text-slate-500 block">Previews Cache</span>
              <span className="text-2xl font-black text-slate-900 mt-1 block">
                {(((storageStats?.usage?.previews_bytes ?? 0) / 1024)).toFixed(1)} KB
              </span>
              <span className="text-xs text-slate-500 mt-1 block">
                {storageStats?.usage?.previews_files ?? 0} cached page images (100 dpi)
              </span>
            </div>

            <div className="bg-slate-50 border border-slate-200 rounded-xl p-4">
              <span className="text-xs font-semibold text-slate-500 block">Templates</span>
              <span className="text-2xl font-black text-slate-900 mt-1 block">
                {(((storageStats?.usage?.templates_bytes ?? 0) / 1024)).toFixed(1)} KB
              </span>
              <span className="text-xs text-slate-500 mt-1 block">
                {storageStats?.usage?.templates_files ?? 0} template source files
              </span>
            </div>
          </div>

          {/* Retention Policy in Plain Words */}
          <div className="bg-brand-50/60 border border-brand-200 rounded-xl p-4 text-xs sm:text-sm text-brand-900 space-y-2">
            <h4 className="font-bold text-brand-900 flex items-center gap-1.5">
              <Info className="w-4 h-4 text-brand-700" /> Storage Retention Policy
            </h4>
            <ul className="list-disc list-inside space-y-1.5 text-brand-900/90 leading-relaxed">
              <li>
                <strong>Document Versions:</strong> Only the latest {storageStats?.retention_settings?.keep_version_files ?? 3} versions of each document maintain physical DOCX and PDF files on disk. Older version rows remain intact and can be re-created on-demand at any time from immutable template versions and snapshots.
              </li>
              <li>
                <strong>Page Previews:</strong> Generated on-demand as lightweight 100 dpi JPEGs and cached for {storageStats?.retention_settings?.preview_ttl_days ?? 7} days. Expired previews are automatically evicted and re-rendered when requested.
              </li>
              <li>
                <strong>Batch ZIP Downloads:</strong> Assembled on demand and cached for {storageStats?.retention_settings?.batch_ttl_hours ?? 24} hours without duplicating existing document files.
              </li>
              <li>
                <strong>Template Sharing:</strong> Duplicate template files are content-addressed by SHA-256 and shared across identical forks.
              </li>
            </ul>
          </div>
        </div>
      )}
    </div>
  );
};
