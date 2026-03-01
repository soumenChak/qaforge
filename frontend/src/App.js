import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './contexts/AuthContext';
import ErrorBoundary from './components/ErrorBoundary';
import Layout from './components/Layout';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Projects from './pages/Projects';
import ProjectDetail from './pages/ProjectDetail';
import TestCaseEditor from './pages/TestCaseEditor';
import TestPlans from './pages/TestPlans';
import TestPlanDetail from './pages/TestPlanDetail';
import Settings from './pages/Settings';
import Users from './pages/Users';
import TemplateManager from './pages/TemplateManager';
import KnowledgeBase from './pages/KnowledgeBase';

/**
 * ProtectedRoute -- Redirects to /login if not authenticated.
 */
function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-fg-gray">
        <div className="text-center">
          <svg className="animate-spin w-8 h-8 text-fg-teal mx-auto mb-3" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <p className="text-sm text-fg-mid">Loading...</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return children;
}

/**
 * AdminRoute -- Requires admin role.
 */
function AdminRoute({ children }) {
  const { isAdmin } = useAuth();

  if (!isAdmin) {
    return (
      <div className="page-container">
        <div className="card-static p-8 text-center">
          <p className="text-fg-mid">You do not have permission to access this page.</p>
        </div>
      </div>
    );
  }

  return children;
}

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <Routes>
          {/* Public route */}
          <Route path="/login" element={<Login />} />

          {/* Protected routes */}
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route index element={<Dashboard />} />
            <Route path="projects" element={<Projects />} />
            <Route path="projects/:id" element={<ProjectDetail />} />
            <Route path="projects/:id/test-plans" element={<TestPlans />} />
            <Route path="projects/:id/test-plans/:planId" element={<TestPlanDetail />} />
            <Route path="projects/:id/test-cases/:tcId" element={<TestCaseEditor />} />
            <Route path="templates" element={<TemplateManager />} />
            <Route path="knowledge" element={<KnowledgeBase />} />
            <Route path="settings" element={<Settings />} />
            <Route
              path="users"
              element={
                <AdminRoute>
                  <Users />
                </AdminRoute>
              }
            />
          </Route>

          {/* Catch-all */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </ErrorBoundary>
  );
}
