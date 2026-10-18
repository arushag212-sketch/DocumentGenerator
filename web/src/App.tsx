import React, { useState, useEffect } from 'react';
import { Routes, Route, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from './context/AuthContext';
import { Header } from './components/Header';
import { AuthPage } from './components/AuthPage';
import { HomePageWrapper } from './pages/HomePageWrapper';
import { DocumentsPage } from './pages/DocumentsPage';
import { DocumentNewPage } from './pages/DocumentNewPage';
import { DocumentDetailPage } from './pages/DocumentDetailPage';
import { TemplatesPage } from './pages/TemplatesPage';
import { TemplateEditorPage } from './pages/TemplateEditorPage';
import { SettingsPage } from './pages/SettingsPage';
import { OnboardingClubPage } from './pages/OnboardingClubPage';
import { OnboardingPositionPage } from './pages/OnboardingPositionPage';
import { JoinRequestsPage } from './pages/JoinRequestsPage';
import { api } from './api/client';
import { ClubPermissions, JoinRequest } from './types';

// Guard component that enforces authentication, club membership, and position assignment
const RequireAuth: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, loading, clubs, activeClub } = useAuth();
  const location = useLocation();
  const [permissions, setPermissions] = useState<ClubPermissions | null>(null);
  const [myJoinRequest, setMyJoinRequest] = useState<JoinRequest | null>(null);
  const [checkingStatus, setCheckingStatus] = useState(false);

  useEffect(() => {
    if (activeClub) {
      setCheckingStatus(true);
      Promise.all([
        api.clubs.getPermissions(activeClub.id).catch(() => null),
        api.clubs.getMyJoinRequest(activeClub.id).catch(() => null),
      ])
        .then(([perms, jr]) => {
          setPermissions(perms);
          setMyJoinRequest(jr);
        })
        .finally(() => setCheckingStatus(false));
    } else {
      setPermissions(null);
      setMyJoinRequest(null);
    }
  }, [activeClub?.id]);

  if (loading || checkingStatus) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center">
        <div className="text-center">
          <div className="h-10 w-10 border-4 border-amber-400 border-t-transparent rounded-full animate-spin mx-auto mb-3"></div>
          <p className="text-slate-400 text-xs font-medium">Loading SVNIT ClubDocs...</p>
        </div>
      </div>
    );
  }

  // 1. Unauthenticated -> redirect to /login preserving deep link and search params
  if (!user) {
    const search = location.search || window.location.search || '';
    return <Navigate to={`/login${search}`} state={{ from: location }} replace />;
  }

  const currentPath = location.pathname;

  // 2. User has no clubs -> redirect to /onboarding/club
  if (clubs.length === 0 && currentPath !== '/onboarding/club') {
    return <Navigate to="/onboarding/club" replace />;
  }

  // 3. User is in club but pending approval without active role -> redirect to /onboarding/club (waiting screen)
  const isPendingApproval = myJoinRequest?.status === 'pending' && !permissions?.role;
  if (isPendingApproval && currentPath !== '/onboarding/club') {
    return <Navigate to="/onboarding/club" replace />;
  }

  // 4. User is active member but position not chosen -> redirect to /onboarding/position
  if (
    permissions?.role &&
    (!permissions.position || permissions.position.trim() === '') &&
    currentPath !== '/onboarding/position' &&
    currentPath !== '/onboarding/club'
  ) {
    return <Navigate to="/onboarding/position" replace />;
  }

  return <>{children}</>;
};

// Layout with Header, Content, Footer
const AppLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <Header onOpenClubModal={() => navigate('/onboarding/club')} />
      <main className="flex-1 w-full">{children}</main>
      <footer className="border-t border-slate-200 bg-white py-4 mt-auto">
        <div className="max-w-7xl mx-auto px-4 text-center text-xs text-slate-500">
          SVNIT ClubDocs System — Built for Student Chapters & Institute Document Workflows
        </div>
      </footer>
    </div>
  );
};

const RootRedirect: React.FC = () => {
  const location = useLocation();
  const search = location.search || window.location.search || '';
  return <Navigate to={`/home${search}`} replace />;
};

export const App: React.FC = () => {
  return (
    <Routes>
      {/* Public route */}
      <Route path="/login" element={<AuthPage />} />

      {/* Onboarding routes (authenticated) */}
      <Route
        path="/onboarding/club"
        element={
          <RequireAuth>
            <AppLayout>
              <OnboardingClubPage />
            </AppLayout>
          </RequireAuth>
        }
      />
      <Route
        path="/onboarding/position"
        element={
          <RequireAuth>
            <AppLayout>
              <OnboardingPositionPage />
            </AppLayout>
          </RequireAuth>
        }
      />

      {/* Main app routes (authenticated) */}
      <Route
        path="/home"
        element={
          <RequireAuth>
            <AppLayout>
              <HomePageWrapper />
            </AppLayout>
          </RequireAuth>
        }
      />
      <Route
        path="/documents"
        element={
          <RequireAuth>
            <AppLayout>
              <DocumentsPage />
            </AppLayout>
          </RequireAuth>
        }
      />
      <Route
        path="/documents/new"
        element={
          <RequireAuth>
            <AppLayout>
              <DocumentNewPage />
            </AppLayout>
          </RequireAuth>
        }
      />
      <Route
        path="/documents/:id"
        element={
          <RequireAuth>
            <AppLayout>
              <DocumentDetailPage />
            </AppLayout>
          </RequireAuth>
        }
      />
      <Route
        path="/templates"
        element={
          <RequireAuth>
            <AppLayout>
              <TemplatesPage />
            </AppLayout>
          </RequireAuth>
        }
      />
      <Route
        path="/templates/:id"
        element={
          <RequireAuth>
            <AppLayout>
              <TemplateEditorPage />
            </AppLayout>
          </RequireAuth>
        }
      />
      <Route
        path="/settings"
        element={<Navigate to="/settings/club" replace />}
      />
      <Route
        path="/settings/:section"
        element={
          <RequireAuth>
            <AppLayout>
              <SettingsPage />
            </AppLayout>
          </RequireAuth>
        }
      />
      <Route
        path="/join-requests"
        element={
          <RequireAuth>
            <AppLayout>
              <JoinRequestsPage />
            </AppLayout>
          </RequireAuth>
        }
      />

      {/* Default redirects */}
      <Route path="/" element={<RootRedirect />} />
      <Route path="*" element={<RootRedirect />} />
    </Routes>
  );
};

export default App;
