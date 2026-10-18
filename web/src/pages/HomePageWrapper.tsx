import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { HomePage } from '../components/HomePage';
import { ResultPage } from '../components/ResultPage';
import { HomeGenerateResponse } from '../types';
import { Building2 } from 'lucide-react';
import { Link } from 'react-router-dom';

export const HomePageWrapper: React.FC = () => {
  const { activeClub } = useAuth();
  const [homeResult, setHomeResult] = useState<HomeGenerateResponse | null>(null);

  if (!activeClub) {
    return (
      <div className="max-w-md mx-auto my-16 bg-white border border-slate-200 rounded-3xl p-8 text-center shadow-sm">
        <div className="w-14 h-14 bg-blue-50 text-[#1b365d] rounded-2xl flex items-center justify-center mx-auto mb-4">
          <Building2 className="w-8 h-8" />
        </div>
        <h2 className="text-lg font-bold text-slate-900">Which club are you in?</h2>
        <p className="text-xs sm:text-sm text-slate-500 mt-1">
          Select an existing student chapter or add your own club to start drafting documents.
        </p>
        <Link
          to="/onboarding/club"
          className="inline-block mt-5 px-5 py-2.5 bg-[#1b365d] hover:bg-[#132742] text-white text-xs sm:text-sm font-bold rounded-xl transition-colors shadow-sm"
        >
          Find or Add Club
        </Link>
      </div>
    );
  }

  if (homeResult) {
    return (
      <ResultPage
        clubId={activeClub.id}
        result={homeResult}
        onEditDetails={() => setHomeResult(null)}
      />
    );
  }

  return (
    <HomePage
      clubId={activeClub.id}
      onDocumentsGenerated={(res) => setHomeResult(res)}
    />
  );
};
