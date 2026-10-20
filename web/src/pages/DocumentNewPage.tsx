import React, { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { HomePage } from '../components/create/HomePage';
import { ResultPage } from '../components/create/ResultPage';
import { RequireCreateAccess } from '../components/layout/RequireCreateAccess';
import { HomeGenerateResponse } from '../types';

export const DocumentNewPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const { activeClub } = useAuth();
  const templateId = searchParams.get('template');
  const initialPrompt = searchParams.get('prompt');
  const [generateResult, setGenerateResult] = useState<HomeGenerateResponse | null>(null);

  if (!activeClub) {
    return (
      <div className="max-w-md mx-auto my-16 bg-white border border-slate-200 rounded-xl p-8 text-center shadow-sm">
        <p className="text-sm text-slate-600">Please select or join a club first to draft documents.</p>
      </div>
    );
  }

  return (
    <RequireCreateAccess>
      <div className={generateResult ? 'hidden' : 'block'}>
        <HomePage
          clubId={activeClub.id}
          initialTemplateId={templateId}
          initialPrompt={initialPrompt}
          onDocumentsGenerated={(res) => setGenerateResult(res)}
        />
      </div>
      {generateResult && (
        <ResultPage
          clubId={activeClub.id}
          result={generateResult}
          onEditDetails={() => setGenerateResult(null)}
        />
      )}
    </RequireCreateAccess>
  );
};
