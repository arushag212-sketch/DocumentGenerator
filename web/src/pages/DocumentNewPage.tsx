import React, { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { HomePage } from '../components/HomePage';
import { ResultPage } from '../components/ResultPage';
import { HomeGenerateResponse } from '../types';

export const DocumentNewPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const { activeClub } = useAuth();
  const templateId = searchParams.get('template');
  const [generateResult, setGenerateResult] = useState<HomeGenerateResponse | null>(null);

  if (!activeClub) {
    return (
      <div className="max-w-md mx-auto my-16 bg-white border border-slate-200 rounded-3xl p-8 text-center shadow-sm">
        <p className="text-sm text-slate-600">Please select or join a club first to draft documents.</p>
      </div>
    );
  }

  if (generateResult) {
    return (
      <ResultPage
        clubId={activeClub.id}
        result={generateResult}
        onEditDetails={() => setGenerateResult(null)}
      />
    );
  }

  return (
    <HomePage
      clubId={activeClub.id}
      initialTemplateId={templateId}
      onDocumentsGenerated={(res) => setGenerateResult(res)}
    />
  );
};
