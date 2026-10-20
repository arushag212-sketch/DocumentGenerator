import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { GoogleSignInButton } from './auth/GoogleSignInButton';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import { Lock, Mail, User, KeyRound, ShieldAlert, CheckCircle2, ArrowRight, Sparkles, FileCheck2, ShieldCheck } from 'lucide-react';
import { DocPreviewArt } from './brand/DocPreviewArt';
const AuthInput: React.FC<{
  icon: any;
  label?: string;
  helper?: string;
  className?: string;
  [key: string]: any;
}> = ({ icon: Icon, label, helper, className = '', ...props }) => (
  <div>
    {label && <label className="block text-xs font-medium text-slate-700 mb-1">{label}</label>}
    <div className="relative">
      <Icon className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
      <input
        {...props}
        className={`w-full pl-9 pr-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-700/30 focus:border-brand-700 ${className}`}
      />
    </div>
    {helper && <p className="text-xs text-slate-400 mt-1">{helper}</p>}
  </div>
);

export const AuthPage: React.FC<{ initialTab?: 'login' | 'register' }> = ({ initialTab }) => {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as any)?.from || '/dashboard';

  const getInviteParam = () => {
    const params = new URLSearchParams(location.search || window.location.search);
    let code = params.get('invite');
    if (!code && (location.state as any)?.from?.search) {
      code = new URLSearchParams((location.state as any).from.search).get('invite');
    }
    return code || '';
  };

  const initialInvite = getInviteParam();
  // Password-reset emails link to /login?reset_token=...
  const initialResetToken = new URLSearchParams(location.search || window.location.search).get('reset_token') || '';
  const [tab, setTab] = useState<'login' | 'register' | 'forgot' | 'reset'>(
    initialResetToken ? 'reset' : initialInvite ? 'register' : (initialTab || 'login'),
  );

  // Form states
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [registerEmail, setRegisterEmail] = useState('');
  const [registerPassword, setRegisterPassword] = useState('');
  const [forgotEmail, setForgotEmail] = useState('');
  const [fullName, setFullName] = useState('');
  const [resetToken, setResetToken] = useState(initialResetToken);
  const [newPassword, setNewPassword] = useState('');
  const [inviteCode, setInviteCode] = useState(initialInvite);
  const [invitePreview, setInvitePreview] = useState<{
    code: string;
    club_name: string;
    role: string;
    is_valid: boolean;
    status: string;
  } | null>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    const inv = getInviteParam();
    if (inv && inv !== inviteCode) {
      setInviteCode(inv);
      setTab('register');
    }
  }, [location.search]);

  useEffect(() => {
    if (inviteCode.trim()) {
      api.invites.preview(inviteCode.trim())
        .then((data) => setInvitePreview(data))
        .catch(() => setInvitePreview(null));
    } else {
      setInvitePreview(null);
    }
  }, [inviteCode]);

  const resetFormFeedback = () => {
    setError(null);
    setSuccess(null);
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    resetFormFeedback();
    setLoading(true);

    try {
      const params = new URLSearchParams();
      params.append('username', loginEmail.trim());
      params.append('password', loginPassword);
      await login(params);

      // If logging in via an invite link, accept the invite
      if (inviteCode.trim()) {
        try {
          await api.invites.accept(inviteCode.trim());
        } catch {
          // Continue if already a member or handled
        }
      }
      navigate(from, { replace: true });
    } catch (err: any) {
      setError(err.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    resetFormFeedback();

    if (registerPassword.length < 10) {
      setError('Password must be at least 10 characters long.');
      return;
    }

    setLoading(true);
    try {
      await api.auth.register({
        email: registerEmail.trim(),
        password: registerPassword,
        full_name: fullName.trim(),
        invite_code: inviteCode.trim() || undefined,
      });
      // Automatically log in after registration
      const params = new URLSearchParams();
      params.append('username', registerEmail.trim());
      params.append('password', registerPassword);
      await login(params);
      navigate(from, { replace: true });
    } catch (err: any) {
      setError(err.message || 'Registration failed');
    } finally {
      setLoading(false);
    }
  };

  const handleForgotPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    resetFormFeedback();
    setLoading(true);

    try {
      const res = await api.auth.forgotPassword(forgotEmail.trim());
      setSuccess(res.message);
    } catch (err: any) {
      setError(err.message || 'Request failed');
    } finally {
      setLoading(false);
    }
  };

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    resetFormFeedback();

    if (newPassword.length < 10) {
      setError('New password must be at least 10 characters long.');
      return;
    }

    setLoading(true);
    try {
      const res = await api.auth.resetPassword(resetToken.trim(), newPassword);
      setSuccess(`${res.message}. You can now sign in with your new password.`);
      setTimeout(() => {
        setTab('login');
        setLoginPassword('');
        resetFormFeedback();
      }, 2500);
    } catch (err: any) {
      setError(err.message || 'Reset token is invalid or expired');
    } finally {
      setLoading(false);
    }
  };

  const heading = {
    login: { title: 'Welcome back', sub: 'Sign in to create and manage your club documents.' },
    register: { title: 'Create your account', sub: 'Use your SVNIT email to join or start a club.' },
    forgot: { title: 'Reset your password', sub: 'We will email you a link that works for 30 minutes.' },
    reset: { title: 'Choose a new password', sub: 'Paste the code from the email, then pick a new password.' },
  }[tab];

  return (
    <div className="min-h-screen bg-slate-50 lg:grid lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)]">
      {/* Brand panel (large screens) */}
      <aside className="relative hidden lg:flex flex-col justify-between overflow-hidden bg-gradient-to-br from-brand-900 via-brand-800 to-brand-700 p-12 text-white">
        <div className="pointer-events-none absolute -right-24 -top-24 h-80 w-80 rounded-full bg-white/5" aria-hidden="true" />
        <div className="pointer-events-none absolute -bottom-32 -left-20 h-96 w-96 rounded-full bg-svnit-gold/10" aria-hidden="true" />

        <Link to="/" className="relative flex items-center gap-3 w-fit">
          <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-white p-1.5 shadow">
            <img src="/brand/svnit_crest.png" alt="" className="h-full w-full object-contain" />
          </span>
          <span>
            <span className="block text-lg font-semibold tracking-tight">ClubDocs</span>
            <span className="block text-xs text-brand-200">SVNIT Surat</span>
          </span>
        </Link>

        <div className="relative grid grid-cols-[1fr_auto] items-center gap-10">
          <div>
            <h2 className="text-3xl xl:text-4xl font-semibold leading-tight tracking-tight">
              Official club documents,
              <br />
              <span className="text-svnit-gold">ready in minutes.</span>
            </h2>
            <ul className="mt-8 space-y-4 text-sm text-brand-100">
              {[
                { icon: Sparkles, text: 'Describe your event once. ClubDocs drafts every letter it needs.' },
                { icon: FileCheck2, text: 'Your club letterhead, reference numbers and signatories, every time.' },
                { icon: ShieldCheck, text: 'Review, approve and verify. Only SVNIT accounts can sign in.' },
              ].map(({ icon: Icon, text }) => (
                <li key={text} className="flex items-start gap-3">
                  <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-white/10">
                    <Icon className="h-4 w-4 text-svnit-gold" />
                  </span>
                  <span className="leading-relaxed">{text}</span>
                </li>
              ))}
            </ul>
          </div>
          <DocPreviewArt className="w-56 xl:w-64" />
        </div>

        <p className="relative text-xs text-brand-200">
          Sardar Vallabhbhai National Institute of Technology, Surat
        </p>
      </aside>

      {/* Sign-in area */}
      <main className="flex min-h-screen flex-col items-center justify-center px-4 py-10 sm:px-8">
        {/* Compact brand (small screens) */}
        <Link to="/" className="mb-8 flex flex-col items-center text-center lg:hidden">
          <span className="flex h-16 w-16 items-center justify-center rounded-2xl bg-white p-2 shadow-sm ring-1 ring-slate-200">
            <img src="/brand/svnit_crest.png" alt="SVNIT crest" className="h-full w-full object-contain" />
          </span>
          <span className="mt-2 text-lg font-semibold text-slate-900">ClubDocs</span>
          <span className="text-xs text-slate-500">SVNIT Surat</span>
        </Link>

        <div className="w-full max-w-[420px]">
          <div className="mb-6">
            <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{heading.title}</h1>
            <p className="mt-1.5 text-sm text-slate-500">{heading.sub}</p>
          </div>

          <div className="surface-card p-6 shadow-sm sm:p-7">
            {(tab === 'login' || tab === 'register') && (
              <div className="mb-6 grid grid-cols-2 rounded-lg bg-slate-100 p-1" role="tablist" aria-label="Sign in or create account">
                {(['login', 'register'] as const).map((t) => (
                  <button
                    key={t}
                    type="button"
                    role="tab"
                    aria-selected={tab === t}
                    onClick={() => {
                      setTab(t);
                      resetFormFeedback();
                    }}
                    className={`rounded-md py-1.5 text-sm font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 ${
                      tab === t ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-800'
                    }`}
                  >
                    {t === 'login' ? 'Sign in' : 'Create account'}
                  </button>
                ))}
              </div>
            )}

            {invitePreview && (
              <div className={`mb-5 p-3 rounded-lg border text-xs flex items-start gap-2.5 ${
                invitePreview.is_valid
                  ? 'bg-brand-50 border-brand-200 text-brand-700'
                  : 'bg-amber-50 border-amber-200 text-amber-800'
              }`}>
                <Mail className="w-4 h-4 flex-shrink-0 mt-0.5" />
                <div>
                  {invitePreview.is_valid ? (
                    <>
                      <p className="font-semibold">You have been invited</p>
                      <p className="mt-0.5">
                        Join <span className="font-semibold">{invitePreview.club_name}</span> as{' '}
                        <span className="font-semibold capitalize">{invitePreview.role}</span>.
                        Sign in or create an account to join.
                      </p>
                    </>
                  ) : (
                    <>
                      <p className="font-bold">Invite {invitePreview.status}</p>
                      <p className="mt-0.5">This invite is no longer active ({invitePreview.status}). Ask your club for a new one.</p>
                    </>
                  )}
                </div>
              </div>
            )}

            {(tab === 'login' || tab === 'register') && (
              <div className="mb-5">
                <GoogleSignInButton
                  inviteCode={inviteCode.trim() || undefined}
                  onSuccess={(_user) => {
                    navigate(from, { replace: true });
                  }}
                  onError={(msg) => {
                    setError(msg);
                  }}
                />
                <p className="text-center text-xs text-slate-500 mt-2">
                  Recommended: one click with your SVNIT Google account (@svnit.ac.in)
                </p>
                <div className="relative mt-5">
                  <div className="absolute inset-0 flex items-center">
                    <div className="w-full border-t border-slate-200" />
                  </div>
                  <div className="relative flex justify-center text-xs">
                    <span className="bg-white px-2.5 text-slate-400 font-medium">or use email and password</span>
                  </div>
                </div>
              </div>
            )}

            {error && (
              <div role="alert" className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-lg flex items-start gap-2">
                <ShieldAlert className="w-4 h-4 flex-shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            )}

            {success && (
              <div role="status" className="mb-4 p-3 bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs rounded-lg flex items-start gap-2">
                <CheckCircle2 className="w-4 h-4 flex-shrink-0 mt-0.5" />
                <span>{success}</span>
              </div>
            )}

            {tab === 'login' && (
              <form onSubmit={handleLogin} className="space-y-4">
                <AuthInput icon={Mail} label="Email" type="email" autoComplete="email" required value={loginEmail} onChange={(e: any) => setLoginEmail(e.target.value)} placeholder="you@svnit.ac.in" />
                <AuthInput icon={Lock} label="Password" type="password" autoComplete="current-password" required value={loginPassword} onChange={(e: any) => setLoginPassword(e.target.value)} placeholder="Your password" />
                <div className="flex justify-end text-xs">
                  <button type="button" onClick={() => { setTab('forgot'); resetFormFeedback(); }} className="text-brand-700 hover:underline">Forgot password?</button>
                </div>
                <button type="submit" disabled={loading} className="btn-primary w-full justify-center py-2.5">
                  {loading ? 'Signing in…' : 'Sign in'}
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </form>
            )}

            {tab === 'register' && (
              <form onSubmit={handleRegister} className="space-y-4">
                <AuthInput icon={User} label="Full name" type="text" autoComplete="name" required value={fullName} onChange={(e: any) => setFullName(e.target.value)} placeholder="Your name" />
                <AuthInput icon={Mail} label="SVNIT email" type="email" autoComplete="email" required value={registerEmail} onChange={(e: any) => setRegisterEmail(e.target.value)} placeholder="you@svnit.ac.in" />
                <AuthInput icon={Lock} label="Password" type="password" autoComplete="new-password" required minLength={10} value={registerPassword} onChange={(e: any) => setRegisterPassword(e.target.value)} placeholder="At least 10 characters" helper="Common passwords are not allowed." />
                <AuthInput icon={KeyRound} label="Club invite code (optional)" type="text" value={inviteCode} onChange={(e: any) => setInviteCode(e.target.value.toUpperCase())} placeholder="e.g. ACM-A7B8C9" className="font-mono uppercase" />
                <button type="submit" disabled={loading} className="btn-primary w-full justify-center py-2.5">
                  {loading ? 'Creating account…' : 'Create account'}
                </button>
              </form>
            )}

            {tab === 'forgot' && (
              <div className="space-y-4">
                <form onSubmit={handleForgotPassword} className="space-y-4">
                  <AuthInput icon={Mail} label="Email" type="email" autoComplete="email" required value={forgotEmail} onChange={(e: any) => setForgotEmail(e.target.value)} placeholder="you@svnit.ac.in" />
                  <button type="submit" disabled={loading} className="btn-primary w-full justify-center py-2.5">
                    {loading ? 'Sending…' : 'Send reset link'}
                  </button>
                </form>
                <div className="pt-3 border-t border-slate-100 flex items-center justify-between text-xs">
                  <button type="button" onClick={() => { setTab('login'); resetFormFeedback(); }} className="text-slate-500 hover:text-slate-800">← Back to sign in</button>
                  <button type="button" onClick={() => { setTab('reset'); resetFormFeedback(); }} className="text-brand-700 hover:underline">I have a reset code</button>
                </div>
              </div>
            )}

            {tab === 'reset' && (
              <form onSubmit={handleResetPassword} className="space-y-4">
                <AuthInput icon={KeyRound} label="Reset code" type="text" required value={resetToken} onChange={(e: any) => setResetToken(e.target.value)} placeholder="Paste the code from the email" className="font-mono" />
                <AuthInput icon={Lock} label="New password" type="password" autoComplete="new-password" required minLength={10} value={newPassword} onChange={(e: any) => setNewPassword(e.target.value)} placeholder="At least 10 characters" />
                <button type="submit" disabled={loading} className="btn-primary w-full justify-center py-2.5">
                  {loading ? 'Updating…' : 'Set new password'}
                </button>
                <div className="text-center pt-1">
                  <button type="button" onClick={() => { setTab('login'); resetFormFeedback(); }} className="text-xs text-slate-500 hover:text-slate-800">← Back to sign in</button>
                </div>
              </form>
            )}
          </div>

          <div className="mt-6 flex items-center justify-center gap-3 text-xs text-slate-400">
            <Link to="/privacy" className="hover:text-slate-600 hover:underline">Privacy</Link>
            <span aria-hidden="true">·</span>
            <Link to="/terms" className="hover:text-slate-600 hover:underline">Terms</Link>
            <span aria-hidden="true">·</span>
            <Link to="/verify" className="hover:text-slate-600 hover:underline">Verify a document</Link>
          </div>
        </div>
      </main>
    </div>
  );
};
