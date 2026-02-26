import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { projectsAPI, feedbackAPI } from '../services/api';
import { DOMAIN_COLORS, DOMAIN_NAMES } from '../constants/domains';
import Spinner from '../components/Spinner';
import StatCard from '../components/StatCard';
import {
  FolderIcon,
  ClipboardDocumentCheckIcon,
  CheckBadgeIcon,
  StarIcon,
  PlusIcon,
  SparklesIcon,
} from '@heroicons/react/24/outline';

export default function Dashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [projects, setProjects] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showProjectPicker, setShowProjectPicker] = useState(false);

  useEffect(() => {
    const loadData = async () => {
      try {
        const [projRes, metricsRes] = await Promise.allSettled([
          projectsAPI.getAll(),
          feedbackAPI.getMetrics({ days: 30 }),
        ]);

        if (projRes.status === 'fulfilled') setProjects(projRes.value.data);
        if (metricsRes.status === 'fulfilled') setMetrics(metricsRes.value.data);
      } catch (err) {
        console.error('Dashboard load error:', err);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, []);

  const totalProjects = projects.length;
  const activeTestCases = projects.reduce((sum, p) => sum + (p.test_case_count || 0), 0);
  const totalPassed = projects.reduce((sum, p) => sum + (p.passed_count || 0), 0);
  const passedRate = activeTestCases > 0
    ? `${Math.round((totalPassed / activeTestCases) * 100)}%`
    : '--';
  const avgRating = metrics?.average_rating
    ? metrics.average_rating.toFixed(1)
    : '--';

  const recentProjects = projects.slice(0, 5);

  if (loading) {
    return (
      <div className="page-container">
        <Spinner />
      </div>
    );
  }

  return (
    <div className="page-container">
      {/* Welcome header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-fg-navy">
          Welcome back, {user?.name?.split(' ')[0] || 'User'}
        </h1>
        <p className="text-sm text-fg-mid mt-1">Here is your QA overview</p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 mb-8">
        <StatCard
          label="Total Projects"
          value={totalProjects}
          icon={FolderIcon}
        />
        <StatCard
          label="Active Test Cases"
          value={activeTestCases}
          icon={ClipboardDocumentCheckIcon}
        />
        <StatCard
          label="Passed Rate"
          value={passedRate}
          icon={CheckBadgeIcon}
          accentFrom="from-green-400"
          accentTo="to-green-600"
        />
        <StatCard
          label="Avg Quality Rating"
          value={avgRating}
          icon={StarIcon}
          accentFrom="from-fg-teal"
          accentTo="to-blue-400"
        />
      </div>

      {/* Quick actions + Recent projects */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Quick Actions */}
        <div className="lg:col-span-1">
          <div className="card-static overflow-visible h-full">
            <div className="h-1 bg-gradient-to-r from-fg-teal to-fg-green rounded-t-xl" />
            <div className="p-6">
            <h3 className="text-sm font-bold text-fg-navy uppercase tracking-wider mb-4">
              Quick Actions
            </h3>
            <div className="space-y-3">
              <button
                onClick={() => navigate('/projects', { state: { openNewModal: true } })}
                className="w-full flex items-center gap-3 px-4 py-3 rounded-lg border border-gray-200 text-sm font-medium text-fg-dark hover:bg-fg-tealLight hover:border-fg-teal/30 transition-all"
              >
                <PlusIcon className="w-5 h-5 text-fg-teal" />
                New Project
              </button>
              {projects.length > 0 && (
                <div className="relative">
                  <button
                    onClick={() => setShowProjectPicker(!showProjectPicker)}
                    className="w-full flex items-center gap-3 px-4 py-3 rounded-lg border border-gray-200 text-sm font-medium text-fg-dark hover:bg-fg-tealLight hover:border-fg-teal/30 transition-all"
                  >
                    <SparklesIcon className="w-5 h-5 text-fg-green" />
                    Generate Test Cases
                  </button>
                  {showProjectPicker && (
                    <div className="absolute left-0 right-0 mt-1 bg-white rounded-lg border border-gray-200 shadow-lg z-10 py-1 max-h-48 overflow-y-auto">
                      <p className="px-3 py-1.5 text-[10px] text-gray-400 uppercase tracking-wider font-semibold">Select project</p>
                      {projects.map((p) => (
                        <button
                          key={p.id}
                          onClick={() => { setShowProjectPicker(false); navigate(`/projects/${p.id}/generate`); }}
                          className="w-full text-left px-3 py-2 text-sm text-fg-dark hover:bg-fg-tealLight transition-colors flex items-center gap-2"
                        >
                          <span className="truncate">{p.name}</span>
                          <span className={`ml-auto text-[10px] px-1.5 py-0.5 rounded-full ${DOMAIN_COLORS[p.domain] || 'bg-gray-100 text-gray-600'}`}>
                            {DOMAIN_NAMES[p.domain] || p.domain}
                          </span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
            </div>
          </div>
        </div>

        {/* Recent Projects table */}
        <div className="lg:col-span-2">
          <div className="card-static overflow-hidden h-full">
            <div className="h-1 bg-gradient-to-r from-fg-teal to-fg-green" />
            <div className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-bold text-fg-navy uppercase tracking-wider">
                  Recent Projects
                </h3>
                {projects.length > 5 && (
                  <button
                    onClick={() => navigate('/projects')}
                    className="text-xs font-medium text-fg-teal hover:text-fg-tealDark"
                  >
                    View all &rarr;
                  </button>
                )}
              </div>

              {recentProjects.length === 0 ? (
                <div className="text-center py-8">
                  <FolderIcon className="w-10 h-10 text-gray-300 mx-auto mb-3" />
                  <p className="text-sm text-fg-mid">
                    No projects yet. Create your first project to get started.
                  </p>
                </div>
              ) : (
                <div className="table-container">
                  <table className="min-w-full">
                    <thead>
                      <tr className="table-header">
                        <th className="px-4 py-2.5">Project</th>
                        <th className="px-4 py-2.5">Domain</th>
                        <th className="px-4 py-2.5 text-center">Test Cases</th>
                        <th className="px-4 py-2.5 text-center">Passed</th>
                        <th className="px-4 py-2.5">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50">
                      {recentProjects.map((p) => {
                        const passRate = (p.test_case_count || 0) > 0
                          ? Math.round(((p.passed_count || 0) / p.test_case_count) * 100)
                          : null;
                        return (
                          <tr
                            key={p.id}
                            className="table-row cursor-pointer"
                            onClick={() => navigate(`/projects/${p.id}`)}
                          >
                            <td className="px-4 py-3 text-sm font-medium text-fg-dark">
                              {p.name}
                            </td>
                            <td className="px-4 py-3">
                              <span className={`badge ${DOMAIN_COLORS[p.domain] || 'badge-gray'}`}>
                                {DOMAIN_NAMES[p.domain] || p.domain}
                              </span>
                            </td>
                            <td className="px-4 py-3 text-sm text-center text-fg-dark font-medium">
                              {p.test_case_count || 0}
                            </td>
                            <td className="px-4 py-3 text-sm text-center">
                              {passRate !== null ? (
                                <span className={passRate >= 70 ? 'text-green-600 font-medium' : 'text-fg-mid'}>
                                  {passRate}%
                                </span>
                              ) : (
                                <span className="text-fg-mid">--</span>
                              )}
                            </td>
                            <td className="px-4 py-3">
                              <span className={`badge ${
                                p.status === 'active' ? 'badge-green' :
                                p.status === 'completed' ? 'badge-teal' :
                                'badge-gray'
                              }`}>
                                {p.status}
                              </span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
