import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import { Lock, Mail, User, KeyRound, ShieldAlert, CheckCircle2, ArrowRight, Sparkles } from 'lucide-react';
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
        className={`w-full pl-9 pr-3 py-2 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500 ${className}`}
      />
    </div>
    {helper && <p className="text-[10px] text-slate-400 mt-1">{helper}</p>}
  </div>
);

export const AuthPage: React.FC = () => {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as any)?.from || '/home';

  const getInviteParam = () => {
    const params = new URLSearchParams(location.search || window.location.search);
    let code = params.get('invite');
    if (!code && (location.state as any)?.from?.search) {
      code = new URLSearchParams((location.state as any).from.search).get('invite');
    }
    return code || '';
  };

  const initialInvite = getInviteParam();
  const [tab, setTab] = useState<'login' | 'register' | 'forgot' | 'reset'>(initialInvite ? 'register' : 'login');

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
    <div className="min-h-screen bg-slate-100 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      {/* Permanent SVNIT Branding in Auth Shell */}
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center">
        <div className="inline-flex items-center justify-center h-20 w-20 rounded-2xl bg-white p-2 shadow-md border border-slate-200 mb-3">
          <img
            src="/assets/svnit_crest.png"
            alt="SVNIT Crest"
            className="h-full w-full object-contain"
            onError={(e) => {
              (e.target as HTMLElement).style.display = 'none';
            }}
          />
        </div>
        <h1 className="text-2xl font-extrabold tracking-tight text-[#1b365d]">SVNIT ClubDocs</h1>
        <p className="mt-1 text-xs text-slate-600">
          Sardar Vallabhbhai National Institute of Technology, Surat
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-white py-8 px-6 shadow-2xl rounded-2xl sm:px-10 border border-slate-100">
          {/* Auth Tabs */}
          <div className="flex border-b border-slate-200 mb-6">
            <button
              type="button"
              onClick={() => {
                setTab('login');
                resetFormFeedback();
              }}
              className={`flex-1 py-2 text-center text-xs font-semibold border-b-2 transition-colors ${
                tab === 'login'
                  ? 'border-amber-500 text-amber-600'
                  : 'border-transparent text-slate-500 hover:text-slate-800'
              }`}
            >
              Sign In
            </button>
            <button
              type="button"
              onClick={() => {
                setTab('register');
                resetFormFeedback();
              }}
              className={`flex-1 py-2 text-center text-xs font-semibold border-b-2 transition-colors ${
                tab === 'register'
                  ? 'border-amber-500 text-amber-600'
                  : 'border-transparent text-slate-500 hover:text-slate-800'
              }`}
            >
              Register
            </button>
            <button
              type="button"
              onClick={() => {
                setTab('forgot');
                resetFormFeedback();
              }}
              className={`flex-1 py-2 text-center text-xs font-semibold border-b-2 transition-colors ${
                tab === 'forgot' || tab === 'reset'
                  ? 'border-amber-500 text-amber-600'
                  : 'border-transparent text-slate-500 hover:text-slate-800'
              }`}
            >
              Forgot Key
            </button>
          </div>

          {invitePreview && (
            <div className={`mb-4 p-3 rounded-lg border text-xs flex items-start gap-2.5 ${
              invitePreview.is_valid
                ? 'bg-blue-50 border-blue-200 text-[#1b365d]'
                : 'bg-amber-50 border-amber-200 text-amber-800'
            }`}>
              <Sparkles className="w-4 h-4 flex-shrink-0 mt-0.5 text-amber-500" />
              <div>
                {invitePreview.is_valid ? (
                  <>
                    <p className="font-bold">You've been invited!</p>
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
              <AuthInput icon={Mail} label="Email Address" type="email" required value={loginEmail} onChange={(e: any) => setLoginEmail(e.target.value)} placeholder="student@example.com" />
              <AuthInput icon={Lock} label="Password" type="password" required value={loginPassword} onChange={(e: any) => setLoginPassword(e.target.value)} placeholder="••••••••••••" />
              <div className="flex items-center justify-between text-[11px]">
                <span className="text-slate-500">HttpOnly cookie session</span>
                <button type="button" onClick={() => { setTab('forgot'); resetFormFeedback(); }} className="text-amber-600 hover:text-amber-700 font-medium">Forgot password?</button>
              </div>
              <button type="submit" disabled={loading} className="w-full bg-slate-900 hover:bg-slate-800 text-white py-2 px-4 rounded-lg text-xs font-semibold transition-colors shadow-sm disabled:opacity-50 flex items-center justify-center gap-2">
                {loading ? 'Authenticating...' : 'Sign In'}
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </form>
          )}

          {/* REGISTER FORM */}
          {tab === 'register' && (
            <form onSubmit={handleRegister} className="space-y-4">
              <AuthInput icon={User} label="Full Name" type="text" required value={fullName} onChange={(e: any) => setFullName(e.target.value)} placeholder="Student Lead" />
              <AuthInput icon={Mail} label="Email" type="email" required value={registerEmail} onChange={(e: any) => setRegisterEmail(e.target.value)} placeholder="lead@example.com" />
              <AuthInput icon={Lock} label="Password (min 10 characters)" type="password" required minLength={10} value={registerPassword} onChange={(e: any) => setRegisterPassword(e.target.value)} placeholder="Min 10 characters" helper="Enforces strong password policy. Common dictionary passwords are rejected." />
              <AuthInput icon={KeyRound} label="Club Invite Code (Optional)" type="text" value={inviteCode} onChange={(e: any) => setInviteCode(e.target.value.toUpperCase())} placeholder="e.g. ACM-A7B8C9" className="font-mono uppercase" />
              <button type="submit" disabled={loading} className="w-full bg-amber-500 hover:bg-amber-600 text-white py-2 px-4 rounded-lg text-xs font-semibold transition-colors shadow-sm disabled:opacity-50">
                {loading ? 'Creating Account...' : 'Create Account'}
              </button>
            </form>
          )}

          {/* FORGOT PASSWORD FORM */}
          {tab === 'forgot' && (
            <div className="space-y-4">
              <form onSubmit={handleForgotPassword} className="space-y-4">
                <AuthInput icon={Mail} label="Registered Email Address" type="email" required value={forgotEmail} onChange={(e: any) => setForgotEmail(e.target.value)} placeholder="student@example.com" helper="Returns enumeration-safe confirmation. Tokens expire in 30 minutes." />
                <button type="submit" disabled={loading} className="w-full bg-slate-900 hover:bg-slate-800 text-white py-2 px-4 rounded-lg text-xs font-semibold transition-colors shadow-sm disabled:opacity-50">
                  {loading ? 'Dispatching...' : 'Send Reset Link'}
                </button>
              </form>
              <div className="pt-3 border-t border-slate-100 flex items-center justify-between text-xs">
                <span className="text-slate-500">Already have a reset token?</span>
                <button type="button" onClick={() => { setTab('reset'); resetFormFeedback(); }} className="text-amber-600 hover:text-amber-700 font-semibold">Enter Token</button>
              </div>
            </div>
          )}

          {/* RESET PASSWORD FORM */}
          {tab === 'reset' && (
            <form onSubmit={handleResetPassword} className="space-y-4">
              <AuthInput icon={KeyRound} label="Reset Token" type="text" required value={resetToken} onChange={(e: any) => setResetToken(e.target.value)} placeholder="Paste one-time token" className="font-mono" />
              <AuthInput icon={Lock} label="New Password (min 10 characters)" type="password" required minLength={10} value={newPassword} onChange={(e: any) => setNewPassword(e.target.value)} placeholder="••••••••••••" />
              <button type="submit" disabled={loading} className="w-full bg-emerald-600 hover:bg-emerald-700 text-white py-2 px-4 rounded-lg text-xs font-semibold transition-colors shadow-sm disabled:opacity-50">
                {loading ? 'Updating Password...' : 'Reset Password'}
              </button>
              <div className="text-center pt-2">
                <button type="button" onClick={() => { setTab('login'); resetFormFeedback(); }} className="text-xs text-slate-500 hover:text-slate-800">Back to Sign In</button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};
