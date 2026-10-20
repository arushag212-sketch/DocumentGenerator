import React, { useEffect, useMemo, useState } from 'react';
import { Person, ClubPermissions } from '../types';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { Eye, EyeOff, Plus, Pencil, Trash2, X, Info, PenLine } from 'lucide-react';

interface PeopleTabProps {
  clubId: string | number;
  permissions: ClubPermissions | null;
}

interface Position {
  key: string;
  label: string;
  group: 'faculty' | 'student' | 'staff' | 'other';
  signs: boolean;
  help: string;
}

const GROUP_LABEL: Record<Position['group'], string> = {
  faculty: 'Faculty',
  student: 'Students',
  staff: 'Staff',
  other: 'Other',
};

type FormState = {
  id?: string | number;
  roleId?: string;
  name: string;
  rollNumber: string;
  branch: string;
  mobile: string;
  mobileChanged: boolean;
  position: string;
  designation: string;
};

const EMPTY_FORM: FormState = {
  name: '',
  rollNumber: '',
  branch: '',
  mobile: '',
  mobileChanged: false,
  position: 'faculty_chairman',
  designation: '',
};

/** 10-digit mobile; spaces, dashes and a +91 prefix are accepted and stripped. */
function normaliseMobile(value: string): string | null {
  let digits = value.replace(/[\s\-()]/g, '');
  if (!digits) return '';
  if (digits.startsWith('+91')) digits = digits.slice(3);
  else if (digits.length === 11 && digits.startsWith('0')) digits = digits.slice(1);
  return /^[0-9]{10}$/.test(digits) ? digits : null;
}

export const PeopleTab: React.FC<PeopleTabProps> = ({ clubId, permissions }) => {
  const { activeClub } = useAuth();
  const [people, setPeople] = useState<Person[]>([]);
  const [positions, setPositions] = useState<Position[]>([]);
  const [revealedMobiles, setRevealedMobiles] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState<FormState | null>(null);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const canEdit = Boolean(permissions?.can_edit_settings);
  const canViewSensitive = permissions?.can_view_sensitive || permissions?.is_platform_admin;
  const positionLabel = useMemo(() => Object.fromEntries(positions.map((p) => [p.key, p.label])), [positions]);
  const academicYear = (activeClub as any)?.academic_year_default || '2026-27';

  const fetchPeople = async () => {
    try {
      setLoading(true);
      setPeople(await api.clubs.getPeople(clubId));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPeople();
    setRevealedMobiles({});
    api.clubs.getPositions(clubId).then(setPositions).catch(() => setPositions([]));
  }, [clubId]);

  const handleReveal = async (personId: string | number) => {
    const key = String(personId);
    if (revealedMobiles[key]) {
      const next = { ...revealedMobiles };
      delete next[key];
      setRevealedMobiles(next);
      return;
    }
    try {
      const res = await api.clubs.revealSensitive(clubId, personId);
      if (res.value) setRevealedMobiles((prev) => ({ ...prev, [key]: res.value || '' }));
    } catch (err: any) {
      setNotice(err?.message || 'You do not have permission to see this number.');
    }
  };

  const openEdit = (p: Person) => {
    const role = p.roles?.[0];
    setFormError(null);
    setForm({
      id: p.id,
      roleId: role?.id,
      name: p.name || '',
      rollNumber: p.roll_number || '',
      branch: p.branch || p.department || '',
      mobile: '',
      mobileChanged: false,
      position: role && positionLabel[role.role_key] ? role.role_key : role ? 'other' : 'other',
      designation: role?.designation_label || p.designation || '',
    });
  };

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form) return;
    setFormError(null);
    let mobile: string | undefined;
    if (!form.id || form.mobileChanged) {
      const m = normaliseMobile(form.mobile);
      if (m === null) {
        setFormError('Mobile number must be exactly 10 digits.');
        return;
      }
      mobile = m;
    }
    const pos = positions.find((p) => p.key === form.position);
    const designation = form.designation.trim() || pos?.label || '';
    if (form.position === 'other' && !form.designation.trim()) {
      setFormError('Enter a designation for this position.');
      return;
    }
    setSaving(true);
    try {
      const details: Record<string, any> = {
        full_name: form.name.trim(),
        roll_no: form.rollNumber.trim(),
        branch: form.branch.trim(),
      };
      if (mobile !== undefined) details.mobile = mobile;
      let personId = form.id;
      if (personId) {
        await api.clubs.updatePerson(clubId, personId, details as any);
      } else {
        const created = await api.clubs.addPerson(clubId, details as any);
        personId = created.id;
      }
      const roleData = { role_key: form.position, designation_label: designation, academic_year: academicYear };
      if (form.roleId) await api.clubs.updateRole(clubId, form.roleId, roleData);
      else await api.clubs.assignRole(clubId, { person_id: String(personId), ...roleData });
      setNotice(form.id ? 'Details updated.' : 'Official added.');
      setForm(null);
      fetchPeople();
    } catch (err: any) {
      const detail = err?.detail;
      setFormError(
        (Array.isArray(detail) && detail[0]?.msg?.replace(/^Value error, /, '')) ||
          detail?.message ||
          (typeof detail === 'string' ? detail : null) ||
          err?.message ||
          'Could not save.'
      );
    } finally {
      setSaving(false);
    }
  };

  const remove = async (p: Person) => {
    if (!window.confirm(`Remove ${p.name} from the club's officials? Documents already generated are not changed.`)) return;
    try {
      await api.clubs.deletePerson(clubId, p.id);
      setNotice(`${p.name} removed.`);
      fetchPeople();
    } catch (err: any) {
      setNotice(err?.detail?.message || err?.message || 'Could not remove.');
    }
  };

  const selected = positions.find((p) => p.key === form?.position);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <h2 className="section-title">Officials and signatories</h2>
          <p className="text-sm text-slate-600 mt-0.5 max-w-2xl">
            Faculty, staff and student office-bearers whose names and designations are printed on documents. They do not need an
            account. Mobile numbers are stored encrypted and shown masked.
          </p>
        </div>
        {canEdit && (
          <button
            type="button"
            onClick={() => {
              setFormError(null);
              setForm({ ...EMPTY_FORM });
            }}
            className="btn-primary"
          >
            <Plus className="w-4 h-4" /> Add official
          </button>
        )}
      </div>

      <div className="flex gap-2.5 rounded-lg border border-slate-200 bg-white p-3 text-sm text-slate-600">
        <Info className="w-4 h-4 text-slate-400 flex-shrink-0 mt-0.5" />
        <p>
          <span className="font-medium text-slate-800">Positions</span> here decide who signs documents.{' '}
          <span className="font-medium text-slate-800">App access</span> (admin, editor, viewer) decides what a member can do in
          ClubDocs and is set under Members. A student head is usually both: an admin in the app and the student head on documents.
        </p>
      </div>

      {notice && <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-2.5 text-sm text-emerald-800">{notice}</div>}

      <div className="surface-card overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-slate-500 text-sm">Loading…</div>
        ) : people.length === 0 ? (
          <div className="p-8 text-center text-slate-500 text-sm">No officials yet. Add the faculty chairman and student head first.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 text-slate-500 border-b border-slate-200">
                <tr>
                  <th className="py-2.5 px-4 font-medium">Name</th>
                  <th className="py-2.5 px-4 font-medium">Position</th>
                  <th className="py-2.5 px-4 font-medium">Branch / department</th>
                  <th className="py-2.5 px-4 font-medium">Roll / ID</th>
                  <th className="py-2.5 px-4 font-medium">Mobile</th>
                  {canEdit && <th className="py-2.5 px-4" />}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {people.map((p) => {
                  const key = String(p.id);
                  const role = p.roles?.[0];
                  const signs = role && positions.find((x) => x.key === role.role_key)?.signs;
                  const isRevealed = Boolean(revealedMobiles[key]);
                  return (
                    <tr key={key} className="hover:bg-slate-50">
                      <td className="py-3 px-4 font-medium text-slate-900">{p.name}</td>
                      <td className="py-3 px-4">
                        <p className="text-slate-800">{role ? positionLabel[role.role_key] || role.role_key.replace(/_/g, ' ') : '—'}</p>
                        {role?.designation_label && role.designation_label !== positionLabel[role.role_key] && (
                          <p className="text-xs text-slate-500">{role.designation_label}</p>
                        )}
                        {signs && (
                          <span className="inline-flex items-center gap-1 text-xs text-brand-700 mt-0.5">
                            <PenLine className="w-3 h-3" /> Signs documents
                          </span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-slate-600">{p.branch || p.department || '—'}</td>
                      <td className="py-3 px-4 font-mono text-xs text-slate-500">{p.roll_number || '—'}</td>
                      <td className="py-3 px-4">
                        {p.mobile ? (
                          <span className="inline-flex items-center gap-1.5">
                            <span className="font-mono text-xs">{isRevealed ? revealedMobiles[key] : p.mobile}</span>
                            {canViewSensitive && (
                              <button
                                type="button"
                                onClick={() => handleReveal(p.id)}
                                className="btn-ghost !p-1"
                                aria-label={isRevealed ? 'Hide number' : 'Show number'}
                                title={isRevealed ? 'Hide number' : 'Show number'}
                              >
                                {isRevealed ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                              </button>
                            )}
                          </span>
                        ) : (
                          <span className="text-slate-400">—</span>
                        )}
                      </td>
                      {canEdit && (
                        <td className="py-3 px-4 text-right whitespace-nowrap">
                          <button type="button" className="btn-ghost !p-1.5" onClick={() => openEdit(p)} aria-label={`Edit ${p.name}`} title="Edit">
                            <Pencil className="w-4 h-4" />
                          </button>
                          <button type="button" className="btn-ghost !p-1.5 hover:!text-red-600" onClick={() => remove(p)} aria-label={`Remove ${p.name}`} title="Remove">
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {form && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-labelledby="official-title">
          <div className="absolute inset-0 bg-slate-900/30" onClick={() => setForm(null)} />
          <form onSubmit={save} className="relative surface-card w-full max-w-lg p-5 space-y-4">
            <div className="flex items-center justify-between">
              <h3 id="official-title" className="section-title">{form.id ? 'Edit official' : 'Add official'}</h3>
              <button type="button" className="btn-ghost !p-1.5" onClick={() => setForm(null)} aria-label="Close">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div>
              <label className="field-label" htmlFor="o-name">Full name</label>
              <input id="o-name" className="input-field" required minLength={2} value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g. Dr. Meera Kulkarni" />
            </div>

            <div className="grid sm:grid-cols-2 gap-3">
              <div>
                <label className="field-label" htmlFor="o-position">Position</label>
                <select id="o-position" className="input-field" value={form.position}
                  onChange={(e) => setForm({ ...form, position: e.target.value })}>
                  {(['faculty', 'student', 'staff', 'other'] as const).map((g) => (
                    <optgroup key={g} label={GROUP_LABEL[g]}>
                      {positions.filter((p) => p.group === g).map((p) => (
                        <option key={p.key} value={p.key}>{p.label}</option>
                      ))}
                    </optgroup>
                  ))}
                </select>
              </div>
              <div>
                <label className="field-label" htmlFor="o-designation">
                  Designation as printed {form.position !== 'other' && <span className="font-normal text-slate-500">(optional)</span>}
                </label>
                <input id="o-designation" className="input-field" value={form.designation}
                  onChange={(e) => setForm({ ...form, designation: e.target.value })}
                  placeholder={selected && selected.key !== 'other' ? selected.label : 'e.g. Head of Department, CSE'} />
              </div>
            </div>
            {selected && <p className="text-xs text-slate-500 -mt-2">{selected.help}</p>}

            <div className="grid sm:grid-cols-2 gap-3">
              <div>
                <label className="field-label" htmlFor="o-branch">Branch / department</label>
                <input id="o-branch" className="input-field" value={form.branch}
                  onChange={(e) => setForm({ ...form, branch: e.target.value })} placeholder="e.g. Computer Science & Engineering" />
              </div>
              <div>
                <label className="field-label" htmlFor="o-roll">Roll / employee ID</label>
                <input id="o-roll" className="input-field" value={form.rollNumber}
                  onChange={(e) => setForm({ ...form, rollNumber: e.target.value })} placeholder="e.g. U22CS041" />
              </div>
            </div>

            <div>
              <label className="field-label" htmlFor="o-mobile">Mobile</label>
              <input
                id="o-mobile"
                className="input-field font-mono"
                type="tel"
                inputMode="numeric"
                maxLength={14}
                value={form.mobile}
                onChange={(e) => setForm({ ...form, mobile: e.target.value.replace(/[^0-9+\s-]/g, ''), mobileChanged: true })}
                placeholder={form.id ? 'Leave blank to keep the saved number' : '10 digits, e.g. 9876543210'}
              />
              <p className="text-xs text-slate-500 mt-1">10 digits. Stored encrypted.</p>
            </div>

            {formError && <p className="text-sm text-red-600" role="alert">{formError}</p>}

            <div className="flex justify-end gap-2 pt-1">
              <button type="button" className="btn-secondary" onClick={() => setForm(null)}>Cancel</button>
              <button type="submit" className="btn-primary" disabled={saving}>{saving ? 'Saving…' : form.id ? 'Save changes' : 'Add official'}</button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
};
