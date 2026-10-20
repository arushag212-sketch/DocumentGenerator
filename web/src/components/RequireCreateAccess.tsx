import React from 'react';
import { Link } from 'react-router-dom';
import { Eye, FileText } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useClubPermissions } from '../hooks/useClubPermissions';

/**
 * Renders children only for members allowed to create documents (editor and above).
 * Viewers get an explanation instead of a form that would fail on submit.
 */
export const RequireCreateAccess: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { activeClub } = useAuth();
  const { permissions, loading } = useClubPermissions();

  if (loading) {
    return (
      <div className="max-w-3xl mx-auto my-16 px-4 space-y-3" aria-busy="true">
        <div className="h-8 w-2/3 rounded-xl bg-slate-200 animate-pulse" />
        <div className="h-32 rounded-xl bg-slate-100 animate-pulse" />
      </div>
    );
  }

  if (permissions?.can_create_documents) return <>{children}</>;

  return (
    <div className="max-w-lg mx-auto my-16 px-4">
      <div className="surface-card p-8 text-center">
        <div className="w-14 h-14 bg-slate-100 text-slate-600 rounded-xl flex items-center justify-center mx-auto mb-4">
          <Eye className="w-7 h-7" />
        </div>
        <h2 className="text-lg font-bold text-slate-900">You have read-only access</h2>
        <p className="text-sm text-slate-500 mt-2 leading-relaxed">
          Your role in <span className="font-semibold text-slate-800">{activeClub?.name}</span> is{' '}
          <span className="font-semibold text-slate-800 capitalize">{permissions?.role || 'viewer'}</span>. Ask a club owner
          or admin to make you an <span className="font-semibold">editor</span> to create documents and templates.
        </p>
        <Link to="/documents" className="btn-primary mt-6">
          <FileText className="w-4 h-4" />
          Browse club documents
        </Link>
      </div>
    </div>
  );
};
