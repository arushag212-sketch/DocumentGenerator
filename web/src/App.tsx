import React, { useState, useEffect, Suspense, lazy } from 'react';
import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { useAuth } from './context/AuthContext';
import { AppShell } from './components/AppShell';
import { AuthPage } from './components/AuthPage';
import { LandingPage } from './pages/LandingPage';
import { api } from './api/client';
import { ClubPermissions } from './types';

// Signed-in pages load on demand, so the landing and sign-in pages stay small
// (the template editor alone pulls in the whole TipTap/ProseMirror stack).
const page = <K extends string>(load: () => Promise<Record<K, React.ComponentType<any>>>, name: K) =>
  lazy(() => load().then((m) => ({ default: m[name] })));
const HomePageWrapper = page(() => import('./pages/HomePageWrapper'), 'HomePageWrapper');
const DocumentsPage = page(() => import('./pages/DocumentsPage'), 'DocumentsPage');
const DocumentNewPage = page(() => import('./pages/DocumentNewPage'), 'DocumentNewPage');
const DocumentDetailPage = page(() => import('./pages/DocumentDetailPage'), 'DocumentDetailPage');
const TemplatesPage = page(() => import('./pages/TemplatesPage'), 'TemplatesPage');
const TemplateEditorPage = page(() => import('./pages/TemplateEditorPage'), 'TemplateEditorPage');
const SettingsPage = page(() => import('./pages/SettingsPage'), 'SettingsPage');
const OnboardingClubPage = page(() => import('./pages/OnboardingClubPage'), 'OnboardingClubPage');
const OnboardingPositionPage = page(() => import('./pages/OnboardingPositionPage'), 'OnboardingPositionPage');
const JoinRequestsPage = page(() => import('./pages/JoinRequestsPage'), 'JoinRequestsPage');
const DashboardPage = page(() => import('./pages/DashboardPage'), 'DashboardPage');
const VerifyPage = page(() => import('./pages/VerifyPage'), 'VerifyPage');
const PrivacyPage = page(() => import('./pages/PrivacyPage'), 'PrivacyPage');
const TermsPage = page(() => import('./pages/TermsPage'), 'TermsPage');
const HelpPage = page(() => import('./pages/HelpPage'), 'HelpPage');

const PageSpinner: React.FC = () => (
  <div className="min-h-screen bg-slate-50 flex items-center justify-center">
    <div className="h-6 w-6 border-2 border-brand-700 border-t-transparent rounded-full animate-spin" role="status" aria-label="Loading" />
  </div>
);

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
    return <PageSpinner />;
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
  const { user, loading } = useAuth();
  const location = useLocation();
  const search = location.search || window.location.search || '';
  if (loading) return <PageSpinner />;
  // Visitors who are not signed in see the public landing page (links with ?invite= still go on to sign-in)
  if (!user && !search && location.pathname === '/') return <LandingPage />;
  return <Navigate to={`${search ? '/home' : '/dashboard'}${search}`} replace />;
};

export const App: React.FC = () => {
  return (
    <Suspense fallback={<PageSpinner />}>
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
        path="/help"
        element={
          <RequireAuth>
            <AppLayout>
              <HelpPage />
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
    </Suspense>
  );
};

export default App;
