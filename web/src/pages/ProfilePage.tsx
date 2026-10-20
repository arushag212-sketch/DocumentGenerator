import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { KeyRound, LogOut, MonitorSmartphone, PlayCircle, ShieldCheck, Users, UserRound, Check } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import { PageHeader } from '../components/layout/AppShell';
import { notify } from '../components/common/Toaster';
import { openWelcomeTour } from '../components/onboarding/WelcomeTour';

const Section: React.FC<{ icon: React.ElementType; title: string; description?: string; children: React.ReactNode }> = ({
  icon: Icon,
  title,
  description,
  children,
}) => (
  <section className="surface-card">
    <div className="flex items-start gap-3 border-b border-slate-100 px-5 py-4">
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-700">
        <Icon className="h-4 w-4" />
      </span>
      <div>
        <h2 className="section-title">{title}</h2>
        {description && <p className="mt-0.5 text-xs text-slate-500">{description}</p>}
      </div>
    </div>
    <div className="px-5 py-5">{children}</div>
  </section>
);

/** Rough strength hint shown while typing a new password (the server enforces the real rules). */
function strength(pw: string): { label: string; width: string; color: string } {
  let score = 0;
  if (pw.length >= 10) score++;
  if (pw.length >= 14) score++;
  if (/[A-Z]/.test(pw) && /[a-z]/.test(pw)) score++;
  if (/\d/.test(pw)) score++;
  if (/[^A-Za-z0-9]/.test(pw)) score++;
  if (pw.length < 10) return { label: 'Too short (at least 10 characters)', width: '20%', color: 'bg-red-500' };
  if (score <= 2) return { label: 'Okay', width: '45%', color: 'bg-amber-500' };
  if (score <= 3) return { label: 'Good', width: '70%', color: 'bg-brand-600' };
  return { label: 'Strong', width: '100%', color: 'bg-emerald-600' };
}

export const ProfilePage: React.FC = () => {
  const { user, updateUser, logout, clubs, activeClub, setActiveClubId } = useAuth();
  const [name, setName] = useState(user?.name || '');
  const [savingName, setSavingName] = useState(false);

  const [currentPw, setCurrentPw] = useState('');
  const [newPw, setNewPw] = useState('');
  const [confirmPw, setConfirmPw] = useState('');
  const [pwError, setPwError] = useState<string | null>(null);
  const [savingPw, setSavingPw] = useState(false);
  const [signingOut, setSigningOut] = useState(false);

  if (!user) return null;
  const hasPassword = Boolean(user.has_password);
  const initials = (user.name || user.email).split(' ').map((w) => w[0]).slice(0, 2).join('').toUpperCase();
  const nameChanged = name.trim() !== '' && name.trim() !== user.name;

  const saveName = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingName(true);
    try {
      const updated = await api.auth.updateProfile(name.trim());
      updateUser(updated);
      setName(updated.name);
      notify('Your name was updated.', 'success');
    } catch (err: any) {
      notify(err.message || 'Could not update your name.', 'error');
    } finally {
      setSavingName(false);
    }
  };

  const savePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setPwError(null);
    if (newPw.length < 10) return setPwError('The new password needs at least 10 characters.');
    if (newPw !== confirmPw) return setPwError('The two new passwords do not match.');
    setSavingPw(true);
    try {
      const res = await api.auth.changePassword(newPw, hasPassword ? currentPw : undefined);
      updateUser(res.user);
      setCurrentPw('');
      setNewPw('');
      setConfirmPw('');
      notify(hasPassword ? 'Password changed. Other devices were signed out.' : 'Password set. You can now also sign in with email.', 'success');
    } catch (err: any) {
      setPwError(err.message || 'Could not change the password.');
    } finally {
      setSavingPw(false);
    }
  };

  const signOutOthers = async () => {
    setSigningOut(true);
    try {
      const res = await api.auth.signOutOthers();
      updateUser(res.user);
      notify('Signed out on all other devices.', 'success');
    } catch (err: any) {
      notify(err.message || 'Could not sign out other devices.', 'error');
    } finally {
      setSigningOut(false);
    }
  };

  const meter = newPw ? strength(newPw) : null;
  const memberships = (user.memberships || []).filter((m) => m.status === 'active');

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:px-8">
      <PageHeader title="Profile" description="Your account details, password and sessions." />

      {/* Identity card */}
      <div className="surface-card mb-6 flex flex-col gap-4 overflow-hidden sm:flex-row sm:items-center">
        <div className="flex items-center gap-4 px-5 py-5">
          <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-brand-700 to-brand-900 text-lg font-semibold text-white">
            {initials}
          </span>
          <div className="min-w-0">
            <p className="truncate text-lg font-semibold text-slate-900">{user.name}</p>
            <p className="truncate text-sm text-slate-500">{user.email}</p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {user.is_platform_admin && <span className="badge border-amber-200 bg-amber-50 text-amber-800">Platform admin</span>}
              {user.uses_google && <span className="badge border-slate-200 bg-slate-50 text-slate-700">Google sign-in</span>}
              {hasPassword && <span className="badge border-slate-200 bg-slate-50 text-slate-700">Email &amp; password</span>}
            </div>
          </div>
        </div>
      </div>

      <div className="space-y-6">
        <Section icon={UserRound} title="Your details" description="Your name appears on documents you create and in the club’s activity log.">
          <form onSubmit={saveName} className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="field-label" htmlFor="profile-name">Full name</label>
              <input id="profile-name" className="input-field" value={name} onChange={(e) => setName(e.target.value)} maxLength={120} autoComplete="name" />
            </div>
            <div>
              <label className="field-label" htmlFor="profile-email">Email</label>
              <input id="profile-email" className="input-field bg-slate-50 text-slate-500" value={user.email} disabled />
              <p className="mt-1 text-xs text-slate-400">Your SVNIT email cannot be changed.</p>
            </div>
            <div className="sm:col-span-2">
              <button type="submit" className="btn-primary" disabled={!nameChanged || savingName}>
                {savingName ? 'Saving…' : 'Save name'}
              </button>
            </div>
          </form>
        </Section>

        <Section
          icon={KeyRound}
          title={hasPassword ? 'Change password' : 'Set a password'}
          description={
            hasPassword
              ? 'Changing it signs you out on every other device.'
              : 'You sign in with Google. A password is optional and lets you sign in with your email too.'
          }
        >
          <form onSubmit={savePassword} className="space-y-4">
            {hasPassword && (
              <div className="max-w-sm">
                <label className="field-label" htmlFor="pw-current">Current password</label>
                <input id="pw-current" type="password" className="input-field" value={currentPw} onChange={(e) => setCurrentPw(e.target.value)} autoComplete="current-password" required />
              </div>
            )}
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="field-label" htmlFor="pw-new">New password</label>
                <input id="pw-new" type="password" className="input-field" value={newPw} onChange={(e) => setNewPw(e.target.value)} autoComplete="new-password" minLength={10} required />
                {meter && (
                  <div className="mt-2">
                    <div className="h-1.5 rounded-full bg-slate-100">
                      <div className={`h-1.5 rounded-full transition-all ${meter.color}`} style={{ width: meter.width }} />
                    </div>
                    <p className="mt-1 text-xs text-slate-500">{meter.label}</p>
                  </div>
                )}
              </div>
              <div>
                <label className="field-label" htmlFor="pw-confirm">Repeat new password</label>
                <input id="pw-confirm" type="password" className="input-field" value={confirmPw} onChange={(e) => setConfirmPw(e.target.value)} autoComplete="new-password" required />
                {confirmPw && newPw === confirmPw && (
                  <p className="mt-1 flex items-center gap-1 text-xs text-emerald-700"><Check className="h-3.5 w-3.5" /> Passwords match</p>
                )}
              </div>
            </div>
            {pwError && <p role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{pwError}</p>}
            <button type="submit" className="btn-primary" disabled={savingPw}>
              {savingPw ? 'Saving…' : hasPassword ? 'Change password' : 'Set password'}
            </button>
          </form>
        </Section>

        <Section icon={Users} title="Your clubs" description="Clubs you belong to and your role in each.">
          {memberships.length === 0 ? (
            <p className="text-sm text-slate-500">
              You are not in a club yet. <Link to="/onboarding/club" className="text-brand-700 hover:underline">Join or start one</Link>.
            </p>
          ) : (
            <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200">
              {memberships.map((m) => {
                const isActive = String(activeClub?.id) === String(m.club_id);
                const known = clubs.some((c) => String(c.id) === String(m.club_id));
                return (
                  <li key={m.club_id} className="flex items-center justify-between gap-3 px-4 py-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-slate-900">{m.club_name}</p>
                      <p className="text-xs capitalize text-slate-500">
                        {m.role}
                        {m.position ? ` · ${m.position}` : ''}
                      </p>
                    </div>
                    {isActive ? (
                      <span className="badge border-emerald-200 bg-emerald-50 text-emerald-700">Current club</span>
                    ) : known ? (
                      <button type="button" className="btn-secondary !py-1.5 text-xs" onClick={() => setActiveClubId(m.club_id)}>
                        Switch to this club
                      </button>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          )}
        </Section>

        <Section icon={ShieldCheck} title="Security & sessions" description="Signed in on a shared lab computer or lost a phone? End those sessions here.">
          <div className="flex flex-wrap gap-3">
            <button type="button" className="btn-secondary" onClick={signOutOthers} disabled={signingOut}>
              <MonitorSmartphone className="h-4 w-4" />
              {signingOut ? 'Signing out…' : 'Sign out on other devices'}
            </button>
            <button type="button" className="btn-danger" onClick={logout}>
              <LogOut className="h-4 w-4" />
              Sign out everywhere
            </button>
          </div>
        </Section>

        <Section icon={PlayCircle} title="Getting help" description="See the short introduction again or read the how-to guides.">
          <div className="flex flex-wrap gap-3">
            <button type="button" className="btn-secondary" onClick={openWelcomeTour}>
              <PlayCircle className="h-4 w-4" />
              Replay the tour
            </button>
            <Link to="/help" className="btn-ghost">Open Help &amp; guide →</Link>
          </div>
        </Section>
      </div>
    </div>
  );
};
