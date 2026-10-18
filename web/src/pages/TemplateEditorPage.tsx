import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { TemplateEditor } from '../components/TemplateEditor/TemplateEditor';

export const TemplateEditorPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { activeClub } = useAuth();

  if (!activeClub) {
    return (
      <div className="max-w-md mx-auto my-16 bg-white border border-slate-200 rounded-3xl p-8 text-center shadow-sm">
        <p className="text-sm text-slate-600">Please select a club to edit templates.</p>
      </div>
    );
  }

  if (!id) {
    return (
      <div className="max-w-md mx-auto my-16 bg-white border border-slate-200 rounded-3xl p-8 text-center shadow-sm">
        <p className="text-sm text-slate-600">Template ID is missing.</p>
      </div>
    );
  }

  return (
    <TemplateEditor
      clubId={String(activeClub.id)}
      templateId={id}
      onBack={() => navigate('/templates')}
    />
  );
};
