import React, { useState, useEffect } from 'react';
import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { useAuth } from './context/AuthContext';
import { AppShell } from './components/AppShell';
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
import { DashboardPage } from './pages/DashboardPage';
import { VerifyPage } from './pages/VerifyPage';
import { PrivacyPage } from './pages/PrivacyPage';
import { TermsPage } from './pages/TermsPage';
import { api } from './api/client';
import { ClubPermissions } from './types';

// Guard component that enforces authentication, club membership, and position assignment
const RequireAuth: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, loading, clubs, activeClub } = useAuth();
  const location = useLocation();
  const [permissions, setPermissions] = useState<ClubPermissions | null>(null);
  // Which club+role the current `permissions` were fetched for; until it matches,
  // treat access as still loading so we never redirect on stale/empty state.
  const [loadedKey, setLoadedKey] = useState<string | null>(null);
  const clubKey = activeClub ? `${activeClub.id}:${activeClub.my_role ?? ''}` : null;

  useEffect(() => {
    if (!activeClub || !clubKey) {
      setPermissions(null);
      setLoadedKey(null);
      return;
    }
    let cancelled = false;
    api.clubs
      .getPermissions(activeClub.id)
      .catch(() => null)
      .then((perms) => {
        if (cancelled) return;
        setPermissions(perms);
        setLoadedKey(clubKey);
      });
    return () => {
      cancelled = true;
    };
  }, [clubKey]);

  const checkingStatus = Boolean(clubKey) && loadedKey !== clubKey;

  if (loading || checkingStatus) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="h-6 w-6 border-2 border-brand-700 border-t-transparent rounded-full animate-spin" role="status" aria-label="Loading" />
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

  // 3. No active role in the selected club (request pending, rejected or withdrawn) -> onboarding,
  //    which shows the live request status or lets the user pick another club.
  const hasActiveRole = Boolean(permissions?.role);
  if (activeClub && !hasActiveRole && currentPath !== '/onboarding/club') {
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

const AppLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => <AppShell>{children}</AppShell>;

const RootRedirect: React.FC = () => {
  const location = useLocation();
  const search = location.search || window.location.search || '';
  return <Navigate to={`${search ? '/home' : '/dashboard'}${search}`} replace />;
};

export const App: React.FC = () => {
  return (
    <Routes>
      {/* Public routes */}
      <Route path="/login" element={<AuthPage />} />
      <Route path="/register" element={<AuthPage initialTab="register" />} />
      <Route path="/privacy" element={<PrivacyPage />} />
      <Route path="/terms" element={<TermsPage />} />
      <Route path="/verify" element={<VerifyPage />} />
      <Route path="/verify/:code" element={<VerifyPage />} />

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
        path="/dashboard"
        element={
          <RequireAuth>
            <AppLayout>
              <DashboardPage />
            </AppLayout>
          </RequireAuth>
        }
      />
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
            <TemplateEditorPage />
          </RequireAuth>
        }
      />
      <Route
        path="/editor/:id"
        element={
          <RequireAuth>
            <TemplateEditorPage />
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
