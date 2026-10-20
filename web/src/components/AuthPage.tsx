import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { GoogleSignInButton } from './auth/GoogleSignInButton';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import { Lock, Mail, User, KeyRound, ShieldAlert, CheckCircle2, ArrowRight } from 'lucide-react';
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
  const [tab, setTab] = useState<'login' | 'register' | 'forgot' | 'reset'>(initialInvite ? 'register' : (initialTab || 'login'));

  // Form states
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [registerEmail, setRegisterEmail] = useState('');
  const [registerPassword, setRegisterPassword] = useState('');
  const [forgotEmail, setForgotEmail] = useState('');
  const [fullName, setFullName] = useState('');
  const [resetToken, setResetToken] = useState('');
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
      setSuccess(
        `${res.message} (Note: in dev mode, the link is logged directly to the server console log).`
      );
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

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-center py-12 px-4 sm:px-6 lg:px-8">
      {/* Permanent SVNIT Branding in Auth Shell */}
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center">
        <div className="inline-flex items-center justify-center h-14 w-14 mb-3">
          <img
            src="/assets/svnit_crest.png"
            alt="SVNIT Crest"
            className="h-full w-full object-contain"
            onError={(e) => {
              (e.target as HTMLElement).style.display = 'none';
            }}
          />
        </div>
        <h1 className="text-xl font-semibold text-slate-900">ClubDocs</h1>
        <p className="mt-1 text-sm text-slate-500">
          Sardar Vallabhbhai National Institute of Technology, Surat
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="surface-card py-7 px-6 sm:px-8">
          {/* Auth Tabs */}
          <div className="flex border-b border-slate-200 mb-6">
            <button
              type="button"
              onClick={() => {
                setTab('login');
                resetFormFeedback();
              }}
              className={`flex-1 py-2 text-center text-sm font-medium border-b-2 transition-colors ${
                tab === 'login'
                  ? 'border-brand-700 text-brand-800'
                  : 'border-transparent text-slate-500 hover:text-slate-800'
              }`}
            >
              Sign in
            </button>
            <button
              type="button"
              onClick={() => {
                setTab('register');
                resetFormFeedback();
              }}
              className={`flex-1 py-2 text-center text-sm font-medium border-b-2 transition-colors ${
                tab === 'register'
                  ? 'border-brand-700 text-brand-800'
                  : 'border-transparent text-slate-500 hover:text-slate-800'
              }`}
            >
              Create account
            </button>
            <button
              type="button"
              onClick={() => {
                setTab('forgot');
                resetFormFeedback();
              }}
              className={`flex-1 py-2 text-center text-sm font-medium border-b-2 transition-colors ${
                tab === 'forgot' || tab === 'reset'
                  ? 'border-brand-700 text-brand-800'
                  : 'border-transparent text-slate-500 hover:text-slate-800'
              }`}
            >
              Reset password
            </button>
          </div>

          {invitePreview && (
            <div className={`mb-4 p-3 rounded-lg border text-xs flex items-start gap-2.5 ${
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
                      Register or sign in to join immediately.
                    </p>
                  </>
                ) : (
                  <>
                    <p className="font-bold">Invite {invitePreview.status}</p>
                    <p className="mt-0.5">This invite is no longer active ({invitePreview.status}). Please request a new invite.</p>
                  </>
                )}
              </div>
            </div>
          )}

          {/* TOP OF LOGIN & REGISTER: Google Sign-in */}
          {(tab === 'login' || tab === 'register') && (
            <div className="mb-4">
              <GoogleSignInButton
                inviteCode={inviteCode.trim() || undefined}
                onSuccess={(_user) => {
                  navigate(from, { replace: true });
                }}
                onError={(msg) => {
                  setError(msg);
                }}
              />
              <p className="text-center text-xs text-slate-500 mt-1.5">
                Use your SVNIT email (@svnit.ac.in)
              </p>
              <div className="relative my-4">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-slate-200" />
                </div>
                <div className="relative flex justify-center text-xs">
                  <span className="bg-white px-2.5 text-slate-400 font-medium">
                    or continue with email
                  </span>
                </div>
              </div>
            </div>
          )}

          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-lg flex items-start gap-2">
              <ShieldAlert className="w-4 h-4 flex-shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {success && (
            <div className="mb-4 p-3 bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs rounded-lg flex items-start gap-2">
              <CheckCircle2 className="w-4 h-4 flex-shrink-0 mt-0.5" />
              <span>{success}</span>
            </div>
          )}

          {/* LOGIN FORM */}
          {tab === 'login' && (
            <form onSubmit={handleLogin} className="space-y-4">
              <AuthInput icon={Mail} label="Email" type="email" required value={loginEmail} onChange={(e: any) => setLoginEmail(e.target.value)} placeholder="student@example.com" />
              <AuthInput icon={Lock} label="Password" type="password" required value={loginPassword} onChange={(e: any) => setLoginPassword(e.target.value)} placeholder="••••••••••••" />
              <div className="flex items-center justify-between text-xs">
                <span />
                <button type="button" onClick={() => { setTab('forgot'); resetFormFeedback(); }} className="text-brand-700 hover:underline">Forgot password?</button>
              </div>
              <button type="submit" disabled={loading} className="btn-primary w-full justify-center">
                {loading ? 'Signing in…' : 'Sign in'}
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </form>
          )}

          {/* REGISTER FORM */}
          {tab === 'register' && (
            <form onSubmit={handleRegister} className="space-y-4">
              <AuthInput icon={User} label="Full name" type="text" required value={fullName} onChange={(e: any) => setFullName(e.target.value)} placeholder="Your name" />
              <AuthInput icon={Mail} label="Email" type="email" required value={registerEmail} onChange={(e: any) => setRegisterEmail(e.target.value)} placeholder="lead@example.com" />
              <AuthInput icon={Lock} label="Password (min 10 characters)" type="password" required minLength={10} value={registerPassword} onChange={(e: any) => setRegisterPassword(e.target.value)} placeholder="Min 10 characters" helper="Use at least 10 characters. Common passwords are not allowed." />
              <AuthInput icon={KeyRound} label="Club invite code (optional)" type="text" value={inviteCode} onChange={(e: any) => setInviteCode(e.target.value.toUpperCase())} placeholder="e.g. ACM-A7B8C9" className="font-mono uppercase" />
              <button type="submit" disabled={loading} className="btn-primary w-full justify-center">
                {loading ? 'Creating account…' : 'Create account'}
              </button>
            </form>
          )}

          {/* FORGOT PASSWORD FORM */}
          {tab === 'forgot' && (
            <div className="space-y-4">
              <form onSubmit={handleForgotPassword} className="space-y-4">
                <AuthInput icon={Mail} label="Email" type="email" required value={forgotEmail} onChange={(e: any) => setForgotEmail(e.target.value)} placeholder="student@example.com" helper="If the address is registered, you will receive a reset link valid for 30 minutes." />
                <button type="submit" disabled={loading} className="btn-primary w-full justify-center">
                  {loading ? 'Sending…' : 'Send reset link'}
                </button>
              </form>
              <div className="pt-3 border-t border-slate-100 flex items-center justify-between text-xs">
                <span className="text-slate-500">Already have a reset token?</span>
                <button type="button" onClick={() => { setTab('reset'); resetFormFeedback(); }} className="text-brand-700 hover:underline">Enter token</button>
              </div>
            </div>
          )}

          {/* RESET PASSWORD FORM */}
          {tab === 'reset' && (
            <form onSubmit={handleResetPassword} className="space-y-4">
              <AuthInput icon={KeyRound} label="Reset token" type="text" required value={resetToken} onChange={(e: any) => setResetToken(e.target.value)} placeholder="Paste one-time token" className="font-mono" />
              <AuthInput icon={Lock} label="New password" type="password" required minLength={10} value={newPassword} onChange={(e: any) => setNewPassword(e.target.value)} placeholder="••••••••••••" />
              <button type="submit" disabled={loading} className="btn-primary w-full justify-center">
                {loading ? 'Updating…' : 'Reset password'}
              </button>
              <div className="text-center pt-2">
                <button type="button" onClick={() => { setTab('login'); resetFormFeedback(); }} className="text-xs text-slate-500 hover:text-slate-800">Back to sign in</button>
              </div>
            </form>
          )}
          {/* Footer links to Privacy and Terms */}
          <div className="mt-6 pt-4 border-t border-slate-100 flex items-center justify-center gap-3 text-xs text-slate-400">
            <Link to="/privacy" className="hover:text-slate-600 hover:underline transition-colors">
              Privacy Policy
            </Link>
            <span>·</span>
            <Link to="/terms" className="hover:text-slate-600 hover:underline transition-colors">
              Terms of Service
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};
