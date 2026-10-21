import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import { UserCheck, ArrowRight, AlertCircle } from 'lucide-react';

const STANDARD_POSITIONS = [
  { id: 'Chairperson', title: 'Chairperson / Head', desc: 'Presides over meetings and signs primary official institute documents' },
  { id: 'Secretary', title: 'Secretary', desc: 'Maintains records, communication, and circulars' },
  { id: 'Treasurer', title: 'Treasurer', desc: 'Oversees financial proposals, bills, and budget approvals' },
  { id: 'Executive Member', title: 'Executive Member', desc: 'Core committee member contributing to event and document workflows' },
  { id: 'Faculty Advisor', title: 'Faculty Advisor', desc: 'Guiding professor responsible for faculty endorsements and approvals' },
];

export const OnboardingPositionPage: React.FC = () => {
  const navigate = useNavigate();
  const { activeClub, refreshClubs } = useAuth();

  const [selectedPosition, setSelectedPosition] = useState<string>('Chairperson');
  const [customPosition, setCustomPosition] = useState<string>('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!activeClub) return;
    api.clubs
      .getPermissions(activeClub.id)
      .then((perms) => {
        if (perms && perms.is_member === false) {
          navigate('/dashboard', { replace: true });
        }
      })
      .catch(() => {});
  }, [activeClub?.id, navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeClub) {
      setError('No active club selected.');
      return;
    }

    const finalPos = selectedPosition === 'Custom' ? customPosition.trim() : selectedPosition;
    if (!finalPos) {
      setError('Please specify your position title.');
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      await api.clubs.updatePosition(activeClub.id, finalPos);
      await refreshClubs();
      navigate('/dashboard');
    } catch (err: any) {
      setError(err.message || 'Failed to update position.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-xl mx-auto my-12 px-4 sm:px-6">
      <div className="bg-white border border-slate-200 rounded-xl p-8 sm:p-10 shadow-sm">
        <div className="text-center mb-8">
          <div className="w-14 h-14 bg-brand-50 text-brand-700 rounded-xl flex items-center justify-center mx-auto mb-4">
            <UserCheck className="w-7 h-7" />
          </div>
          <h1 className="text-2xl font-bold text-slate-900">What is your role in {activeClub?.name || 'the club'}?</h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-2">
            Select your official position. This title will be used for document sign-offs and signature blocks.
          </p>
        </div>

        {error && (
          <div className="mb-6 p-3 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700 flex items-start gap-2">
            <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2.5">
            {STANDARD_POSITIONS.map((pos) => {
              const isSelected = selectedPosition === pos.id;
              return (
                <label
                  key={pos.id}
                  className={`flex items-start p-3.5 border rounded-xl cursor-pointer transition-all ${
                    isSelected
                      ? 'border-brand-700 bg-brand-50/50 shadow-sm ring-1 ring-brand-700'
                      : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50/50'
                  }`}
                >
                  <input
                    type="radio"
                    name="position"
                    value={pos.id}
                    checked={isSelected}
                    onChange={() => setSelectedPosition(pos.id)}
                    className="mt-1 h-4 w-4 text-brand-700 focus:ring-brand-700 border-slate-300"
                  />
                  <div className="ml-3">
                    <span className="block text-xs sm:text-sm font-bold text-slate-900">{pos.title}</span>
                    <span className="block text-xs text-slate-500 mt-0.5">{pos.desc}</span>
                  </div>
                </label>
              );
            })}

            <label
              className={`flex items-start p-3.5 border rounded-xl cursor-pointer transition-all ${
                selectedPosition === 'Custom'
                  ? 'border-brand-700 bg-brand-50/50 shadow-sm ring-1 ring-brand-700'
                  : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50/50'
              }`}
            >
              <input
                type="radio"
                name="position"
                value="Custom"
                checked={selectedPosition === 'Custom'}
                onChange={() => setSelectedPosition('Custom')}
                className="mt-1 h-4 w-4 text-brand-700 focus:ring-brand-700 border-slate-300"
              />
              <div className="ml-3 flex-1">
                <span className="block text-xs sm:text-sm font-bold text-slate-900">Other Custom Role</span>
                <span className="block text-xs text-slate-500 mt-0.5">Type your specific designation</span>
                {selectedPosition === 'Custom' && (
                  <input
                    type="text"
                    placeholder="e.g. Technical Lead, Event Manager"
                    value={customPosition}
                    onChange={(e) => setCustomPosition(e.target.value)}
                    required
                    className="mt-2 w-full text-xs sm:text-sm px-3 py-2 border border-slate-200 rounded-xl focus:ring-2 focus:ring-brand-700 focus:outline-none bg-white"
                  />
                )}
              </div>
            </label>
          </div>

          <div className="pt-4">
            <button
              type="submit"
              disabled={submitting}
              className="w-full py-3 px-4 bg-brand-700 hover:bg-brand-800 text-white text-xs sm:text-sm font-bold rounded-xl transition-colors shadow-sm flex items-center justify-center gap-2 disabled:opacity-50"
            >
              {submitting ? 'Saving Position...' : 'Confirm & Go to Home'}
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
