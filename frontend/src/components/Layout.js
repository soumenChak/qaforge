import React, { useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

import {
  HomeIcon,
  FolderIcon,
  ClipboardDocumentCheckIcon,
  BookOpenIcon,
  BeakerIcon,
  QuestionMarkCircleIcon,
  CogIcon,
  UsersIcon,
  Bars3Icon,
  XMarkIcon,
  ArrowRightOnRectangleIcon,
} from '@heroicons/react/24/outline';

const NAV_ITEMS = [
  { path: '/', label: 'Dashboard', icon: HomeIcon, end: true },
  { path: '/projects', label: 'Projects', icon: FolderIcon },
  { path: '/reviews', label: 'Review Queue', icon: ClipboardDocumentCheckIcon },
  { path: '/knowledge', label: 'Knowledge Base', icon: BookOpenIcon },
  { path: '/frameworks', label: 'Frameworks', icon: BeakerIcon },
  { path: '/guide', label: 'Guide', icon: QuestionMarkCircleIcon },
];

const ADMIN_NAV_ITEMS = [
  { path: '/settings', label: 'Settings', icon: CogIcon },
  { path: '/users', label: 'Users', icon: UsersIcon },
];

export default function Layout() {
  const { user, logout, isAdmin } = useAuth();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  // navItems no longer merges admin items; admin section is rendered separately

  const initials = user?.name
    ? user.name
        .split(' ')
        .map((w) => w[0])
        .slice(0, 2)
        .join('')
        .toUpperCase()
    : 'U';

  const roleBadge = isAdmin ? 'Admin' : 'Engineer';

  const SidebarContent = () => (
    <div className="flex flex-col h-full">
      {/* Logo */}
      <div className="px-6 pt-6 pb-1 flex items-baseline gap-1">
        <span className="text-2xl font-black text-fg-teal tracking-tight">QA</span>
        <span className="text-2xl font-black text-white tracking-tight">Forge</span>
        <span className="text-[10px] text-gray-500 ml-1">by <span className="text-gray-400 font-semibold">FreshGravity</span></span>
      </div>

      {/* Subtitle */}
      <div className="px-6 mb-6">
        <p className="text-[9px] text-gray-500 uppercase tracking-[0.2em]">Where Quality Is Engineered</p>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 space-y-1">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.end}
            onClick={() => setSidebarOpen(false)}
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium transition-all duration-150
              ${isActive
                ? 'bg-gradient-to-r from-fg-teal/20 to-fg-green/15 text-white shadow-sm'
                : 'text-gray-300 hover:text-white hover:bg-white/10'
              }`
            }
          >
            {({ isActive }) => (
              <>
                <item.icon className={`w-5 h-5 flex-shrink-0 ${isActive ? 'text-fg-teal' : ''}`} />
                <span>{item.label}</span>
                {isActive && (
                  <div className="ml-auto w-1.5 h-1.5 rounded-full bg-fg-teal" />
                )}
              </>
            )}
          </NavLink>
        ))}

        {/* Admin section */}
        {isAdmin && (
          <>
            <div className="pt-4 pb-1 px-4">
              <p className="text-[10px] text-gray-500 uppercase tracking-widest font-semibold">Admin</p>
            </div>
            {ADMIN_NAV_ITEMS.map((item) => (
              <NavLink
                key={item.path}
                to={item.path}
                end={item.end}
                onClick={() => setSidebarOpen(false)}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium transition-all duration-150
                  ${isActive
                    ? 'bg-gradient-to-r from-fg-teal/20 to-fg-green/15 text-white shadow-sm'
                    : 'text-gray-300 hover:text-white hover:bg-white/10'
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    <item.icon className={`w-5 h-5 flex-shrink-0 ${isActive ? 'text-fg-teal' : ''}`} />
                    <span>{item.label}</span>
                    {isActive && (
                      <div className="ml-auto w-1.5 h-1.5 rounded-full bg-fg-teal" />
                    )}
                  </>
                )}
              </NavLink>
            ))}
          </>
        )}
      </nav>

      {/* User info + logout at bottom */}
      <div className="mt-auto border-t border-white/10">
        <div className="p-4">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-full bg-gradient-to-br from-fg-teal to-fg-green flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
              {initials}
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-white truncate">{user?.name || 'User'}</p>
              <span className="inline-block text-xxs px-1.5 py-0.5 rounded bg-white/15 text-gray-300 font-medium capitalize">
                {roleBadge}
              </span>
            </div>
            <button
              onClick={handleLogout}
              title="Sign Out"
              className="flex-shrink-0 p-2 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 transition-all duration-150"
            >
              <ArrowRightOnRectangleIcon className="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <div className="flex h-screen overflow-hidden bg-fg-gray">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar -- mobile: slide-in overlay; desktop: fixed */}
      <aside
        className={`
          fixed inset-y-0 left-0 z-50 w-64
          bg-gradient-to-b from-fg-navy via-fg-dark to-fg-navy
          transition-transform duration-300 ease-in-out
          lg:translate-x-0 lg:static lg:flex-shrink-0
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
        `}
      >
        {/* Mobile close button */}
        <button
          onClick={() => setSidebarOpen(false)}
          className="absolute top-4 right-4 lg:hidden text-gray-400 hover:text-white"
        >
          <XMarkIcon className="w-5 h-5" />
        </button>

        <SidebarContent />
      </aside>

      {/* Main content area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Mobile top bar */}
        <div className="lg:hidden flex items-center justify-between bg-white shadow-sm px-4 py-3 flex-shrink-0">
          <button
            onClick={() => setSidebarOpen(true)}
            className="text-fg-dark hover:text-fg-teal"
          >
            <Bars3Icon className="w-6 h-6" />
          </button>
          <div className="flex items-center gap-1">
            <span className="text-lg font-black text-fg-teal">QA</span>
            <span className="text-lg font-black text-fg-navy">Forge</span>
          </div>
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-fg-teal to-fg-green flex items-center justify-center text-white text-xs font-bold">
            {initials}
          </div>
        </div>

        {/* Scrollable page content */}
        <main className="flex-1 overflow-y-auto scrollbar-thin">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
