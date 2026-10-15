import React, { useState, useEffect } from 'react';
import { useAuth } from './context/AuthContext';
import { Header } from './components/Header';
import { Dashboard } from './components/Dashboard';
import { MembersTab } from './components/MembersTab';
import { PeopleTab } from './components/PeopleTab';
import { AuditTab } from './components/AuditTab';
import { SetupWizardModal } from './components/SetupWizardModal';
import { AuthPage } from './components/AuthPage';
import { ClubMember, ClubPermissions, GeneratedDocument } from './types';
import { api } from './api/client';
import { NewDocumentPage } from './components/NewDocumentPage';
import { ReviewDocumentPage } from './components/ReviewDocumentPage';
import { EventsTab } from './components/EventsTab';

export const MainApp: React.FC = () => {
  const { user, loading, activeClub, refreshClubs } = useAuth();
  const [currentTab, setCurrentTab] = useState('dashboard');
  const [members, setMembers] = useState<ClubMember[]>([]);
  const [permissions, setPermissions] = useState<ClubPermissions | null>(null);
  const [showSetupWizard, setShowSetupWizard] = useState(false);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null);
  const [currentDoc, setCurrentDoc] = useState<GeneratedDocument | null>(null);

  const fetchClubData = async () => {
    if (!activeClub) return;
    try {
      const [membersData, permsData] = await Promise.all([
        api.clubs.getMembers(activeClub.id),
        api.clubs.getPermissions(activeClub.id),
      ]);
      setMembers(membersData);
      setPermissions(permsData);
    } catch {
      // If permission or member fetch fails
    }
  };

  useEffect(() => {
    fetchClubData();
  }, [activeClub?.id]);

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center">
        <div className="text-center">
          <div className="h-10 w-10 border-4 border-amber-400 border-t-transparent rounded-full animate-spin mx-auto mb-3"></div>
          <p className="text-slate-400 text-xs font-medium">Loading SVNIT ClubDocs...</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return <AuthPage />;
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <Header
        currentTab={currentTab}
        setCurrentTab={setCurrentTab}
        memberCount={members.length}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {currentTab === 'dashboard' && (
          currentDoc && activeClub ? (
            <ReviewDocumentPage
              clubId={activeClub.id}
              document={currentDoc}
              onBackToDashboard={() => {
                setCurrentDoc(null);
                setSelectedTemplateId(null);
              }}
            />
          ) : selectedTemplateId && activeClub ? (
            <NewDocumentPage
              clubId={activeClub.id}
              templateId={selectedTemplateId}
              onCancel={() => setSelectedTemplateId(null)}
              onGenerated={(doc) => {
                setCurrentDoc(doc);
                setSelectedTemplateId(null);
              }}
            />
          ) : (
            <Dashboard
              permissions={permissions}
              onOpenSetupWizard={() => setShowSetupWizard(true)}
              onSelectTemplate={(templateId) => {
                setSelectedTemplateId(templateId);
                setCurrentDoc(null);
              }}
            />
          )
        )}

        {currentTab === 'events' && activeClub && (
          <EventsTab
            clubId={activeClub.id}
            onViewDocument={(doc) => {
              setCurrentDoc(doc);
              setCurrentTab('dashboard');
            }}
          />
        )}

        {currentTab === 'members' && activeClub && (
          <MembersTab
            clubId={activeClub.id}
            members={members}
            permissions={permissions}
            onRefresh={fetchClubData}
          />
        )}

        {currentTab === 'people' && activeClub && (
          <PeopleTab clubId={activeClub.id} permissions={permissions} />
        )}

        {currentTab === 'audit' && activeClub && (
          <AuditTab clubId={activeClub.id} />
        )}
      </main>

      {/* Setup Wizard Modal */}
      {showSetupWizard && activeClub && (
        <SetupWizardModal
          club={activeClub}
          onClose={() => setShowSetupWizard(false)}
          onSuccess={() => {
            refreshClubs();
            fetchClubData();
          }}
        />
      )}

      {/* Footer */}
      <footer className="border-t border-slate-200 bg-white py-4 mt-auto">
        <div className="max-w-7xl mx-auto px-4 text-center text-xs text-slate-500">
          SVNIT ClubDocs System — Built for Student Chapters & Institute Document Workflows
        </div>
      </footer>
    </div>
  );
};

export const App: React.FC = () => {
  return <MainApp />;
};

export default App;
