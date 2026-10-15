import React, { useState } from 'react';
import { Club } from '../types';
import { api } from '../api/client';
import { Wand2, X, Building, User, CreditCard } from 'lucide-react';

interface SetupWizardModalProps {
  club: Club;
  onClose: () => void;
  onSuccess: () => void;
}

export const SetupWizardModal: React.FC<SetupWizardModalProps> = ({
  club,
  onClose,
  onSuccess,
}) => {
  const [department, setDepartment] = useState(club.department);
  const [academicYear, setAcademicYear] = useState(club.academic_year);

  // Faculty in charge
  const [facultyName, setFacultyName] = useState('Demo Faculty In-Charge');
  const [facultyDesignation, setFacultyDesignation] = useState('Assistant Professor');
  const [facultyMobile, setFacultyMobile] = useState('');

  // Student head
  const [studentName, setStudentName] = useState('Demo Student Head');
  const [studentRoll, setStudentRoll] = useState('DEMO-001');
  const [studentBranch, setStudentBranch] = useState('DoCSE');
  const [studentMobile, setStudentMobile] = useState('');

  // Bank
  const [bankAccountName, setBankAccountName] = useState(`${club.name} SVNIT`);
  const [bankName, setBankName] = useState('State Bank of India, SVNIT Branch');
  const [accountNumber, setAccountNumber] = useState('');
  const [ifscCode, setIfscCode] = useState('SBIN0003320');

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      await api.clubs.setupWizard(club.id, {
        department,
        academic_year: academicYear,
        faculty_in_charge: {
          name: facultyName,
          designation: facultyDesignation,
          mobile: facultyMobile || undefined,
        },
        student_head: {
          name: studentName,
          roll_number: studentRoll,
          branch: studentBranch,
          mobile: studentMobile || undefined,
        },
        bank_details: {
          account_name: bankAccountName,
          bank_name: bankName,
          account_number: accountNumber || undefined,
          ifsc_code: ifscCode,
        },
      });
      onSuccess();
      onClose();
    } catch (err: any) {
      setError(err.message || 'Setup wizard failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4 overflow-y-auto">
      <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full p-6 space-y-6 my-8">
        <div className="flex items-start justify-between border-b border-slate-100 pb-4">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-full bg-amber-100 text-amber-700 flex items-center justify-center">
              <Wand2 className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-900">Club Onboarding & Setup Wizard</h2>
              <p className="text-xs text-slate-500">
                Configure primary metadata, faculty leadership, and official signatories for <strong>{club.name}</strong>.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 p-1 rounded-lg"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {error && (
          <div className="p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-lg">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6 text-xs">
          {/* Section 1: Academic & Dept */}
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-slate-800 font-semibold text-xs border-b border-slate-100 pb-1">
              <Building className="w-4 h-4 text-amber-600" />
              1. Department & Academic Session
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block font-medium text-slate-700 mb-1">Department</label>
                <input
                  type="text"
                  required
                  value={department}
                  onChange={(e) => setDepartment(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-amber-500"
                />
              </div>
              <div>
                <label className="block font-medium text-slate-700 mb-1">Academic Year</label>
                <input
                  type="text"
                  required
                  value={academicYear}
                  onChange={(e) => setAcademicYear(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-amber-500"
                />
              </div>
            </div>
          </div>

          {/* Section 2: Leadership */}
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-slate-800 font-semibold text-xs border-b border-slate-100 pb-1">
              <User className="w-4 h-4 text-amber-600" />
              2. Faculty In-Charge & Student Leadership
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="block font-medium text-slate-700 mb-1">Faculty In-Charge Name</label>
                <input
                  type="text"
                  required
                  value={facultyName}
                  onChange={(e) => setFacultyName(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-amber-500"
                />
              </div>
              <div>
                <label className="block font-medium text-slate-700 mb-1">Designation</label>
                <input
                  type="text"
                  value={facultyDesignation}
                  onChange={(e) => setFacultyDesignation(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-amber-500"
                />
              </div>
              <div>
                <label className="block font-medium text-slate-700 mb-1">Faculty Mobile (Encrypted)</label>
                <input
                  type="tel"
                  value={facultyMobile}
                  onChange={(e) => setFacultyMobile(e.target.value)}
                  placeholder="Optional contact"
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-amber-500"
                />
              </div>
            </div>

            <div className="grid grid-cols-4 gap-3">
              <div>
                <label className="block font-medium text-slate-700 mb-1">Student Head Name</label>
                <input
                  type="text"
                  required
                  value={studentName}
                  onChange={(e) => setStudentName(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-amber-500"
                />
              </div>
              <div>
                <label className="block font-medium text-slate-700 mb-1">Roll Number</label>
                <input
                  type="text"
                  required
                  value={studentRoll}
                  onChange={(e) => setStudentRoll(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-amber-500"
                />
              </div>
              <div>
                <label className="block font-medium text-slate-700 mb-1">Branch</label>
                <input
                  type="text"
                  value={studentBranch}
                  onChange={(e) => setStudentBranch(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-amber-500"
                />
              </div>
              <div>
                <label className="block font-medium text-slate-700 mb-1">Student Mobile</label>
                <input
                  type="tel"
                  value={studentMobile}
                  onChange={(e) => setStudentMobile(e.target.value)}
                  placeholder="Optional contact"
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-amber-500"
                />
              </div>
            </div>
          </div>

          {/* Section 3: Financial Details */}
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-slate-800 font-semibold text-xs border-b border-slate-100 pb-1">
              <CreditCard className="w-4 h-4 text-amber-600" />
              3. Official Bank Account (Bill Settlement)
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block font-medium text-slate-700 mb-1">Account Holder Name</label>
                <input
                  type="text"
                  value={bankAccountName}
                  onChange={(e) => setBankAccountName(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-amber-500"
                />
              </div>
              <div>
                <label className="block font-medium text-slate-700 mb-1">Bank Name & Branch</label>
                <input
                  type="text"
                  value={bankName}
                  onChange={(e) => setBankName(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-amber-500"
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block font-medium text-slate-700 mb-1">Account Number (Encrypted)</label>
                <input
                  type="text"
                  value={accountNumber}
                  onChange={(e) => setAccountNumber(e.target.value)}
                  placeholder="Optional"
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-amber-500"
                />
              </div>
              <div>
                <label className="block font-medium text-slate-700 mb-1">IFSC Code</label>
                <input
                  type="text"
                  value={ifscCode}
                  onChange={(e) => setIfscCode(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-amber-500"
                />
              </div>
            </div>
          </div>

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-slate-300 rounded-lg text-slate-700 hover:bg-slate-50 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-5 py-2 bg-amber-500 hover:bg-amber-600 text-white rounded-lg font-semibold transition-colors shadow-sm disabled:opacity-50"
            >
              {loading ? 'Saving Onboarding Data...' : 'Complete Setup Wizard'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
