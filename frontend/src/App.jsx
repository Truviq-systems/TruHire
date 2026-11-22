import React, { lazy, Suspense, useState, useEffect, useCallback } from 'react';
import { BrowserRouter, Routes, Route, Navigate, Outlet, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ThemeProvider } from './context/ThemeContext';
import { MetaProvider } from './context/MetaContext';

import Sidebar from './components/Sidebar';
import Navbar from './components/Navbar';
import ErrorBoundary from './components/ui/ErrorBoundary';

const TruHireAssistant = lazy(() => import('./components/TruHireAssistant'));
const AuthPage = lazy(() => import('./pages/AuthPage'));
const IngestionPage = lazy(() => import('./pages/IngestionPage'));
const IngestionHistoryPage = lazy(() => import('./pages/IngestionHistoryPage'));
const JobDescriptionsPage = lazy(() => import('./pages/JobDescriptionsPage'));
const SearchPage = lazy(() => import('./pages/SearchPage'));
const CandidateDetailPage = lazy(() => import('./pages/CandidateDetailPage'));
const CandidateHistoryPage = lazy(() => import('./pages/CandidateHistoryPage'));
const TrackerPage = lazy(() => import('./pages/TrackerPage'));
const InterviewsPage = lazy(() => import('./pages/InterviewsPage'));
const InsightsPage = lazy(() => import('./pages/InsightsPage'));
const EmailPage = lazy(() => import('./pages/EmailPage'));
const AIAuditPage = lazy(() => import('./pages/AIAuditPage'));
import { isAdmin } from './lib/review';
import { DEFAULT_ROUTE, PAGES, sectionPath } from './config/pages';
import { STORAGE_KEYS } from './config/env';

// Old paths of any page (bookmarks, links) redirect to where it lives now.
const ALIASES = Object.values(PAGES).flatMap((page) => (page.aliases || []).map((alias) => [alias, page.path]));

const SIDEBAR_PREF_KEY = STORAGE_KEYS.sidebarCollapsed;

const isMobile = () => window.matchMedia('(max-width: 768px)').matches;

function readSidebarPref() {
  try {
    const stored = localStorage.getItem(SIDEBAR_PREF_KEY);
    return stored === null ? isMobile() : stored === '1';  // phones start with the narrow icon rail
  } catch {
    return isMobile();
  }
}

// Protected layout wrapper
function AdminOnly({ children }) {
  const { user } = useAuth();
  return isAdmin(user) ? children : <Navigate to={DEFAULT_ROUTE} replace />;
}

function ProtectedLayout() {
  const { isAuthenticated, loading } = useAuth();
  const location = useLocation();
  // Collapsed (icons only) vs expanded; remembered across navigation and reloads. The arrow under the logo is the only control.
  const [sidebarCollapsed, setSidebarCollapsed] = useState(readSidebarPref);

  useEffect(() => {
    try {
      localStorage.setItem(SIDEBAR_PREF_KEY, sidebarCollapsed ? '1' : '0');
    } catch {
      // Storage unavailable (private mode): the preference just lasts for this session.
    }
  }, [sidebarCollapsed]);

  const toggleSidebar = useCallback(() => setSidebarCollapsed((c) => !c), []);

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ fontSize: '1rem', fontWeight: 600 }}>Loading TruHire...</div>
      </div>
    );
  }

  if (!isAuthenticated) {
    // Remember where the user was headed so login can return them there.
    return <Navigate to={PAGES.login.path} replace state={{ from: { path: `${location.pathname}${location.search}` } }} />;
  }

  return (
    <div className="app-container">
      <Sidebar collapsed={sidebarCollapsed} onToggle={toggleSidebar} />
      <div className="app-workspace">
        <Navbar />
        <div className="app-body">
          <div className="main-content">
            <ErrorBoundary key={`${location.pathname}${location.search}`}>
              <Suspense fallback={<div className="page-body" role="status">Loading…</div>}><Outlet /></Suspense>
            </ErrorBoundary>
          </div>
        </div>
      </div>
      <Suspense fallback={null}><TruHireAssistant /></Suspense>
    </div>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <MetaProvider>
        <BrowserRouter>
          <Routes>
            <Route path={PAGES.login.path} element={<Suspense fallback={null}><AuthPage /></Suspense>} />

            <Route element={<ProtectedLayout />}>
              <Route path="/" element={<Navigate to={DEFAULT_ROUTE} replace />} />
              <Route path={PAGES.ingestion.path} element={<IngestionPage />} />
              <Route path={PAGES.ingestionHistory.path} element={<IngestionHistoryPage />} />
              <Route path={PAGES.requirements.path} element={<JobDescriptionsPage />} />
              {ALIASES.map(([alias, path]) => <Route key={alias} path={alias} element={<Navigate to={path} replace />} />)}
              <Route path={PAGES.search.path} element={<SearchPage />} />
              <Route path={PAGES.email.path} element={<EmailPage />} />
              <Route path={PAGES.candidateHistory.path} element={<CandidateHistoryPage />} />
              <Route path={`${PAGES.candidate.path}/:id`} element={<CandidateDetailPage />} />
              <Route path={PAGES.tracker.path} element={<TrackerPage />} />
              <Route path={sectionPath('tracker', ':kind')} element={<TrackerPage />} />
              <Route path={PAGES.interviews.path} element={<InterviewsPage />} />
              <Route path={sectionPath('interviews', ':kind')} element={<InterviewsPage />} />
              <Route path={PAGES.analytics.path} element={<InsightsPage />} />
              <Route path={PAGES.aiAudit.path} element={<AdminOnly><AIAuditPage /></AdminOnly>} />
            </Route>

            <Route path="*" element={<Navigate to={DEFAULT_ROUTE} replace />} />
          </Routes>
        </BrowserRouter>
        </MetaProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}
