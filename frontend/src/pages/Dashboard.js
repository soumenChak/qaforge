import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { projectsAPI, reviewsAPI } from '../services/api';
import { DOMAIN_COLORS, DOMAIN_NAMES } from '../constants/domains';
import Spinner from '../components/Spinner';
import StatCard from '../components/StatCard';
import {
  FolderIcon,
  CheckBadgeIcon,
  InboxStackIcon,
  BookOpenIcon,
  ArrowRightIcon,
} from '@heroicons/react/24/outline';

export default function Dashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [projects, setProjects] = useState([]);
  const [reviewCounts, setReviewCounts] = useState({ tc_pending: 0, exec_pending: 0 });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadData = async () => {
      try {
        const [projRes, reviewRes] = await Promise.allSettled([
          projectsAPI.getAll(),
          reviewsAPI.getPending(),
        ]);

        if (projRes.status === 'fulfilled') setProjects(projRes.value.data);
        if (reviewRes.status === 'fulfilled') {
          setReviewCounts(reviewRes.value.data.counts || { tc_pending: 0, exec_pending: 0 });
        }
      } catch (err) {
        console.error('Dashboard load error:', err);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, []);

  const pendingReviews = reviewCounts.tc_pending + reviewCounts.exec_pending;
  const activeProjects = projects.filter((p) => p.status === 'active').length;
  const totalTestCases = projects.reduce((sum, p) => sum + (p.test_case_count || 0), 0);
  const totalPassed = projects.reduce((sum, p) => sum + (p.passed_count || 0), 0);
  const passRate = totalTestCases > 0
    ? `${Math.round((totalPassed / totalTestCases) * 100)}%`
    : '--';
  const kbEntries = totalTestCases;

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
          label="Pending Reviews"
          value={pendingReviews}
          icon={InboxStackIcon}
          accentFrom="from-amber-400"
          accentTo="to-orange-500"
        />
        <StatCard
          label="Active Projects"
          value={activeProjects}
          icon={FolderIcon}
        />
        <StatCard
          label="Pass Rate"
          value={passRate}
          icon={CheckBadgeIcon}
          accentFrom="from-green-400"
          accentTo="to-green-600"
        />
        <StatCard
          label="KB Entries"
          value={kbEntries}
          icon={BookOpenIcon}
          accentFrom="from-fg-teal"
          accentTo="to-blue-400"
        />
      </div>

      {/* Pending Reviews + My Projects */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Pending Reviews */}
        <div className="lg:col-span-1">
          <div className="card-static overflow-visible h-full">
            <div className="h-1 bg-gradient-to-r from-amber-400 to-orange-500 rounded-t-xl" />
            <div className="p-6 flex flex-col justify-between h-full">
              <div>
                <h3 className="text-sm font-bold text-fg-navy uppercase tracking-wider mb-4">
                  Pending Reviews
                </h3>
                <p className="text-sm text-fg-mid">
                  <span className="font-semibold text-fg-dark">{reviewCounts.tc_pending}</span> test case{reviewCounts.tc_pending !== 1 ? 's' : ''} and{' '}
                  <span className="font-semibold text-fg-dark">{reviewCounts.exec_pending}</span> execution{reviewCounts.exec_pending !== 1 ? 's' : ''} awaiting review
                </p>
              </div>
              <button
                onClick={() => navigate('/reviews')}
                className="mt-4 w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg bg-fg-teal text-white text-sm font-medium hover:bg-fg-tealDark transition-all"
              >
                Go to Review Queue
                <ArrowRightIcon className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>

        {/* My Projects table */}
        <div className="lg:col-span-2">
          <div className="card-static overflow-hidden h-full">
            <div className="h-1 bg-gradient-to-r from-fg-teal to-fg-green" />
            <div className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-bold text-fg-navy uppercase tracking-wider">
                  My Projects
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
                        const rowPassRate = (p.test_case_count || 0) > 0
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
                              {rowPassRate !== null ? (
                                <span className={rowPassRate >= 70 ? 'text-green-600 font-medium' : 'text-fg-mid'}>
                                  {rowPassRate}%
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

      {/* Agent Activity */}
      <div className="card-static overflow-hidden mt-6">
        <div className="h-1 bg-gradient-to-r from-fg-teal to-fg-green" />
        <div className="p-6">
          <h3 className="text-sm font-bold text-fg-navy uppercase tracking-wider mb-4">
            Recent Agent Activity
          </h3>
          <p className="text-sm text-fg-mid">Agent activity feed coming soon.</p>
        </div>
      </div>
    </div>
  );
}
