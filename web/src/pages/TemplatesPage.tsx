import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { TemplateGalleryTab } from '../components/TemplateGalleryTab';
import { useClubPermissions } from '../hooks/useClubPermissions';
import { documentNewUrl } from '../utils/templatePrompt';

export const TemplatesPage: React.FC = () => {
  const navigate = useNavigate();
  const { activeClub } = useAuth();
  const { permissions } = useClubPermissions();

  if (!activeClub) {
    return (
      <div className="max-w-md mx-auto my-16 bg-white border border-slate-200 rounded-3xl p-8 text-center shadow-sm">
        <p className="text-sm text-slate-600">Please select or join a club first to browse templates.</p>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
      <TemplateGalleryTab
        clubId={activeClub.id}
        permissions={permissions}
        onSelectTemplate={(templateId) => {
          navigate(documentNewUrl(templateId));
        }}
        onOpenEditor={(templateId) => {
          navigate(`/templates/${templateId}`);
        }}
      />
    </div>
  );
};
