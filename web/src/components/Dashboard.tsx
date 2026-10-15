import React from 'react';
import { useAuth } from '../context/AuthContext';
import { ClubPermissions } from '../types';
import { FileText, Wand2, Shield, Calendar, Hash, Building } from 'lucide-react';

interface DashboardProps {
  permissions: ClubPermissions | null;
  onOpenSetupWizard: () => void;
  onSelectTemplate: (templateId: string) => void;
}

export const Dashboard: React.FC<DashboardProps> = ({
  permissions,
  onOpenSetupWizard,
  onSelectTemplate,
}) => {
  const { activeClub } = useAuth();

  if (!activeClub) {
    return (
      <div className="p-8 text-center text-slate-500">
        No active club selected. Please select a club from the switcher above.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Top Banner / Club Profile Card */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-slate-900">{activeClub.name}</h1>
              <span className="bg-blue-50 text-blue-700 text-xs px-2.5 py-1 rounded-full font-mono font-semibold border border-blue-200">
                {activeClub.code || activeClub.short_name || 'ACM'}
              </span>
            </div>
            <div className="flex flex-wrap items-center gap-y-1 gap-x-4 mt-2 text-sm text-slate-600">
              <span className="flex items-center gap-1.5">
                <Building className="w-4 h-4 text-slate-400" />
                Department: <strong>{activeClub.department || 'Computer Science & Engineering'}</strong>
              </span>
              <span className="flex items-center gap-1.5">
                <Calendar className="w-4 h-4 text-slate-400" />
                Academic Year: <strong>{activeClub.academic_year || activeClub.academic_year_default || '2026-27'}</strong>
              </span>
              <span className="flex items-center gap-1.5">
                <Shield className="w-4 h-4 text-slate-400" />
                Your Role:{' '}
                <strong className="capitalize text-slate-800">
                  {permissions?.role || 'Member'}
                </strong>
                {permissions?.is_platform_admin && (
                  <span className="ml-1.5 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider bg-amber-100 text-amber-800 rounded-full border border-amber-300">
                    Platform Admin
                  </span>
                )}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {permissions?.can_edit_settings && (
              <button
                type="button"
                onClick={onOpenSetupWizard}
                className="inline-flex items-center gap-2 bg-amber-500 hover:bg-amber-600 text-white px-4 py-2 rounded-lg text-sm font-semibold shadow-sm transition-colors"
              >
                <Wand2 className="w-4 h-4" />
                Club Setup Wizard
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Numbering Suggestion Counters */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Room Permission Series
            </span>
            <Hash className="w-4 h-4 text-slate-400" />
          </div>
          <div className="mt-2 text-2xl font-bold text-slate-900 font-mono">
            #{String(activeClub.room_counter || 0).padStart(3, '0')}
          </div>
          <p className="mt-1 text-xs text-slate-500">
            Suggested: <code className="text-amber-700 font-semibold">{activeClub.code || activeClub.short_name || 'ACM'}/{activeClub.academic_year || activeClub.academic_year_default || '2026-27'}/ROOM/{String((activeClub.room_counter || 0) + 1).padStart(3, '0')}</code>
          </p>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Event Approval Series
            </span>
            <Hash className="w-4 h-4 text-slate-400" />
          </div>
          <div className="mt-2 text-2xl font-bold text-slate-900 font-mono">
            #{String(activeClub.event_counter || 0).padStart(3, '0')}
          </div>
          <p className="mt-1 text-xs text-slate-500">
            Suggested: <code className="text-amber-700 font-semibold">{activeClub.code || activeClub.short_name || 'ACM'}/{activeClub.academic_year || activeClub.academic_year_default || '2026-27'}/SIH/{String((activeClub.event_counter || 0) + 1).padStart(3, '0')}</code>
          </p>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              MoM Series
            </span>
            <Hash className="w-4 h-4 text-slate-400" />
          </div>
          <div className="mt-2 text-2xl font-bold text-slate-900 font-mono">
            #{String(activeClub.mom_counter || 0).padStart(3, '0')}
          </div>
          <p className="mt-1 text-xs text-slate-500">
            Suggested: <code className="text-amber-700 font-semibold">{activeClub.code || activeClub.short_name || 'ACM'}/{activeClub.academic_year || activeClub.academic_year_default || '2026-27'}/MOM/{String((activeClub.mom_counter || 0) + 1).padStart(3, '0')}</code>
          </p>
        </div>
      </div>

      {/* Official 5+1 Document Suite Grid */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-lg font-bold text-slate-900">Standard SVNIT Document Suite</h2>
            <p className="text-xs text-slate-500">
              Select any document to draft, pre-fill with AI, and render official Word & PDF formats.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[
            {
              templateId: 'permission_letter',
              title: 'Permission Letter',
              code: 'ROOM / LAB',
              desc: 'Single-line header with SVNIT & Student Chapter logos. Explicit room and time permissions.',
              pages: '1 Page',
            },
            {
              templateId: 'approval_note',
              title: 'Event Approval Note',
              code: 'APPROVAL NOTE',
              desc: 'Fits exactly on 1 page. Subject row, budget breakdown, and 2x2 official approval signatures.',
              pages: '1 Page',
            },
            {
              templateId: 'bill_certificate',
              title: 'Bill Certificate',
              code: 'FORM BC-R',
              desc: 'Two-page voucher with line-item breakdowns, tax calculations, and certifier signature line.',
              pages: '2 Pages',
            },
            {
              templateId: 'bill_summary',
              title: 'Bill Summary',
              code: 'EXPENSE RECAP',
              desc: 'Auto-computes Grand Total across all prize winners and operational payees.',
              pages: '1 Page',
            },
            {
              templateId: 'prize_money_receipt',
              title: 'Prize Money Receipts',
              code: 'WINNER VOUCHERS',
              desc: 'One voucher per winner with amount in words, bank account, and revenue stamp box.',
              pages: 'Per-winner',
            },
            {
              templateId: 'mom',
              title: 'Minutes of Meeting (MoM)',
              code: 'MOM SERIES',
              desc: 'Meeting minutes recording event sanction, budget approvals, and committee members present.',
              pages: '1 Page',
            },
          ].map((doc) => (
            <div
              key={doc.templateId}
              onClick={() => onSelectTemplate(doc.templateId)}
              className="border border-slate-200 rounded-lg p-5 hover:border-[#1b365d] hover:shadow-md hover:bg-blue-50/20 transition-all bg-white cursor-pointer group flex flex-col justify-between"
            >
              <div>
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2">
                    <FileText className="w-5 h-5 text-amber-600 group-hover:text-[#1b365d] transition-colors" />
                    <h3 className="font-bold text-slate-900 text-sm group-hover:text-[#1b365d] transition-colors">{doc.title}</h3>
                  </div>
                  <span className="text-[10px] font-mono font-medium text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded border border-slate-200">
                    {doc.pages}
                  </span>
                </div>
                <p className="mt-2 text-xs text-slate-600 leading-relaxed">{doc.desc}</p>
              </div>

              <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs">
                <span className="text-[11px] font-mono text-slate-400">{doc.code}</span>
                <span className="inline-flex items-center gap-1 text-xs font-bold text-[#1b365d] group-hover:underline">
                  New Document →
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
