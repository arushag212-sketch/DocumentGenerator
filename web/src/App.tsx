import React, { useState, useEffect } from 'react';
import { useAuth } from './context/AuthContext';
import { Header } from './components/Header';
import { Dashboard } from './components/Dashboard';
import { MembersTab } from './components/MembersTab';
import { PeopleTab } from './components/PeopleTab';
import { AuditTab } from './components/AuditTab';
import { AdminTab } from './components/AdminTab';
import { SetupWizardModal } from './components/SetupWizardModal';
import { AuthPage } from './components/AuthPage';
import { ClubMember, ClubPermissions, GeneratedDocument, HomeGenerateResponse, JoinRequest } from './types';
import { api } from './api/client';
import { HomePage } from './components/HomePage';
import { ResultPage } from './components/ResultPage';
import { ClubSelectionModal } from './components/ClubSelectionModal';
import { Clock, Building2 } from 'lucide-react';
import { NewDocumentPage } from './components/NewDocumentPage';
import { ReviewDocumentPage } from './components/ReviewDocumentPage';
import { EventsTab } from './components/EventsTab';
import { DocumentsTab } from './components/DocumentsTab';
import { TemplateGalleryTab } from './components/TemplateGalleryTab';
import { TemplateEditor } from './components/TemplateEditor/TemplateEditor';

export const MainApp: React.FC = () => {
  const { user, loading, activeClub, refreshClubs, setActiveClubId } = useAuth();
  const [currentTab, setCurrentTab] = useState('home');
  const [showClubModal, setShowClubModal] = useState(false);
  const [homeResult, setHomeResult] = useState<HomeGenerateResponse | null>(null);
  const [myJoinRequest, setMyJoinRequest] = useState<JoinRequest | null>(null);
  const [members, setMembers] = useState<ClubMember[]>([]);
  const [permissions, setPermissions] = useState<ClubPermissions | null>(null);
  const [showSetupWizard, setShowSetupWizard] = useState(false);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null);
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [editingTemplateId, setEditingTemplateId] = useState<string | null>(null);
  const [currentDoc, setCurrentDoc] = useState<GeneratedDocument | null>(null);

  const fetchClubData = async () => {
    if (!activeClub) {
      setMembers([]);
      setPermissions(null);
      setMyJoinRequest(null);
      return;
    }
    try {
      const [membersData, permsData, myJr] = await Promise.all([
        api.clubs.getMembers(activeClub.id).catch(() => []),
        api.clubs.getPermissions(activeClub.id).catch(() => null),
        api.clubs.getMyJoinRequest(activeClub.id).catch(() => null),
      ]);
      setMembers(membersData);
      setPermissions(permsData);
      setMyJoinRequest(myJr);
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

  const isPendingApproval = myJoinRequest?.status === 'pending' && !permissions?.role;

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <Header
        currentTab={currentTab}
        setCurrentTab={setCurrentTab}
        memberCount={members.length}
        onOpenClubModal={() => setShowClubModal(true)}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {!activeClub ? (
          <div className="max-w-md mx-auto my-16 bg-white border border-slate-200 rounded-2xl p-8 text-center shadow-sm">
            <div className="w-14 h-14 bg-blue-50 text-[#1b365d] rounded-2xl flex items-center justify-center mx-auto mb-4">
              <Building2 className="w-8 h-8" />
            </div>
            <h2 className="text-lg font-bold text-slate-900">Which club are you in?</h2>
            <p className="text-xs sm:text-sm text-slate-500 mt-1">
              Select an existing student chapter or add your own club to start drafting documents.
            </p>
            <button
              type="button"
              onClick={() => setShowClubModal(true)}
              className="mt-5 px-5 py-2.5 bg-[#1b365d] hover:bg-[#132742] text-white text-xs sm:text-sm font-bold rounded-xl transition-colors shadow-sm"
            >
              Find or Add Club
            </button>
          </div>
        ) : isPendingApproval ? (
          <div className="max-w-md mx-auto my-16 bg-white border border-amber-200 rounded-2xl p-8 text-center shadow-sm">
            <div className="w-14 h-14 bg-amber-50 text-amber-600 rounded-2xl flex items-center justify-center mx-auto mb-4">
              <Clock className="w-8 h-8 animate-pulse" />
            </div>
            <h2 className="text-lg font-bold text-slate-900">Waiting for approval</h2>
            <p className="text-xs sm:text-sm text-slate-600 mt-2 leading-relaxed">
              Your request to join <strong>{activeClub.name}</strong> as <strong>{myJoinRequest.position}</strong> is waiting for approval from <strong>{myJoinRequest.admin_name || 'the club administrator'}</strong>.
            </p>
            <p className="text-xs text-slate-400 mt-3">
              Private club documents and drafting actions will be unlocked once approved.
            </p>
            <button
              type="button"
              onClick={() => setShowClubModal(true)}
              className="mt-6 px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-semibold rounded-xl transition-colors"
            >
              Switch or join another club
            </button>
          </div>
        ) : editingTemplateId && activeClub ? (
          <TemplateEditor
            clubId={String(activeClub.id)}
            templateId={editingTemplateId}
            onBack={() => {
              setEditingTemplateId(null);
              fetchClubData();
            }}
          />
        ) : (
          <>
            {currentTab === 'home' && activeClub && (
              homeResult ? (
                <ResultPage
                  clubId={activeClub.id}
                  result={homeResult}
                  onEditDetails={() => setHomeResult(null)}
                />
              ) : (
                <HomePage
                  clubId={activeClub.id}
                  initialTemplateId={selectedTemplateId}
                  onDocumentsGenerated={(res) => setHomeResult(res)}
                />
              )
            )}

            {currentTab === 'dashboard' && (
              currentDoc && activeClub ? (
                <ReviewDocumentPage
                  clubId={activeClub.id}
                  document={currentDoc}
                  onBackToDashboard={() => {
                    setCurrentDoc(null);
                    setSelectedTemplateId(null);
                    setSelectedEventId(null);
                  }}
                />
              ) : selectedTemplateId && activeClub ? (
                <NewDocumentPage
                  clubId={activeClub.id}
                  templateId={selectedTemplateId}
                  eventId={selectedEventId}
                  onCancel={() => {
                    setSelectedTemplateId(null);
                    setSelectedEventId(null);
                  }}
                  onGenerated={(doc) => {
                    setCurrentDoc(doc);
                    setSelectedTemplateId(null);
                    setSelectedEventId(null);
                  }}
                />
              ) : (
                <Dashboard
                  permissions={permissions}
                  onOpenSetupWizard={() => setShowSetupWizard(true)}
                  onSelectTemplate={(templateId) => {
                    setSelectedTemplateId(templateId);
                    setSelectedEventId(null);
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
                onNewDocumentForEvent={(templateId, eventId) => {
                  setSelectedTemplateId(templateId);
                  setSelectedEventId(eventId);
                  setCurrentDoc(null);
                  setCurrentTab('dashboard');
                }}
              />
            )}

            {currentTab === 'documents' && activeClub && (
              <DocumentsTab
                clubId={activeClub.id}
                onViewDocument={(doc) => {
                  setCurrentDoc(doc);
                  setCurrentTab('dashboard');
                }}
                onNavigateToEvents={() => setCurrentTab('events')}
              />
            )}

            {currentTab === 'templates' && activeClub && (
              <TemplateGalleryTab
                clubId={activeClub.id}
                permissions={permissions}
                onSelectTemplate={(templateId) => {
                  setSelectedTemplateId(templateId);
                  setHomeResult(null);
                  setCurrentDoc(null);
                  setCurrentTab('home');
                }}
                onOpenEditor={(templateId) => {
                  setEditingTemplateId(templateId);
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

            {currentTab === 'admin' && activeClub && (
              <AdminTab
                clubId={activeClub.id}
                permissions={permissions}
                members={members}
                onRefreshMembers={fetchClubData}
              />
            )}

            {currentTab === 'audit' && activeClub && (
              <AuditTab clubId={activeClub.id} />
            )}
          </>
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

      {/* Club Selection Modal */}
      <ClubSelectionModal
        isOpen={showClubModal}
        onClose={() => setShowClubModal(false)}
        onClubSelected={async (clubId) => {
          await refreshClubs();
          setActiveClubId(clubId);
          fetchClubData();
          setShowClubModal(false);
        }}
      />

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
