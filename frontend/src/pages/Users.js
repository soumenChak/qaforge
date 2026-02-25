import React, { useState, useEffect, useCallback } from 'react';
import { usersAPI, authAPI } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { PlusIcon, XMarkIcon, PencilIcon, UsersIcon } from '@heroicons/react/24/outline';

const ROLE_COLORS = {
  admin: 'bg-red-100 text-red-700',
  lead: 'bg-blue-100 text-blue-700',
  tester: 'bg-green-100 text-green-700',
};

export default function Users() {
  const { user: currentUser, isAdmin } = useAuth();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [editData, setEditData] = useState({});

  // Add user form
  const [newUser, setNewUser] = useState({ name: '', email: '', password: '', roles: ['tester'] });
  const [addError, setAddError] = useState('');
  const [adding, setAdding] = useState(false);

  const loadUsers = useCallback(async () => {
    try {
      const res = await usersAPI.getAll();
      setUsers(res.data);
    } catch (err) {
      console.error('Failed to load users:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadUsers(); }, [loadUsers]);

  const handleAdd = async (e) => {
    e.preventDefault();
    if (!newUser.name || !newUser.email || !newUser.password) {
      setAddError('All fields are required.');
      return;
    }
    setAdding(true);
    setAddError('');
    try {
      await authAPI.register(newUser);
      setShowAddModal(false);
      setNewUser({ name: '', email: '', password: '', roles: ['tester'] });
      loadUsers();
    } catch (err) {
      setAddError(err.response?.data?.detail || 'Failed to add user.');
    } finally {
      setAdding(false);
    }
  };

  const handleEditStart = (u) => {
    setEditingId(u.id);
    setEditData({ name: u.name, roles: u.roles || ['tester'] });
  };

  const handleEditSave = async (userId) => {
    try {
      await usersAPI.update(userId, editData);
      setEditingId(null);
      loadUsers();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to update user.');
    }
  };

  const handleDeactivate = async (userId, email) => {
    if (!window.confirm(`Deactivate user ${email}?`)) return;
    try {
      await usersAPI.delete(userId);
      loadUsers();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to deactivate user.');
    }
  };

  const toggleRole = (role) => {
    const current = editData.roles || [];
    if (current.includes(role)) {
      setEditData({ ...editData, roles: current.filter((r) => r !== role) });
    } else {
      setEditData({ ...editData, roles: [...current, role] });
    }
  };

  if (!isAdmin) {
    return (
      <div className="page-container">
        <div className="card-static p-8 text-center">
          <p className="text-fg-mid">You do not have permission to manage users.</p>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="page-container">
        <div className="flex items-center justify-center py-20">
          <svg className="animate-spin w-8 h-8 text-fg-teal" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        </div>
      </div>
    );
  }

  return (
    <div className="page-container">
      <div className="section-header">
        <div>
          <h1 className="text-2xl font-bold text-fg-navy">Users</h1>
          <p className="text-sm text-fg-mid mt-1">{users.length} user{users.length !== 1 ? 's' : ''}</p>
        </div>
        <button onClick={() => setShowAddModal(true)} className="btn-primary flex items-center gap-2">
          <PlusIcon className="w-4 h-4" />
          Add User
        </button>
      </div>

      {/* Users table */}
      <div className="card-static overflow-hidden">
        <div className="h-1 bg-gradient-to-r from-fg-teal to-fg-green" />
        <div className="table-container">
          <table className="min-w-full divide-y divide-gray-100">
            <thead>
              <tr className="table-header">
                <th className="px-4 py-3">Name</th>
                <th className="px-4 py-3">Email</th>
                <th className="px-4 py-3">Roles</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {users.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-10 text-center">
                    <UsersIcon className="w-10 h-10 text-gray-300 mx-auto mb-3" />
                    <p className="text-sm text-fg-mid">No users found.</p>
                  </td>
                </tr>
              )}
              {users.map((u) => {
                const isEditing = editingId === u.id;
                const isSelf = currentUser?.id === u.id;

                return (
                  <tr key={u.id} className="table-row">
                    <td className="px-4 py-3">
                      {isEditing ? (
                        <input
                          value={editData.name}
                          onChange={(e) => setEditData({ ...editData, name: e.target.value })}
                          className="input-field text-sm py-1"
                        />
                      ) : (
                        <span className="text-sm font-medium text-fg-dark">{u.name}</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm text-fg-mid">{u.email}</td>
                    <td className="px-4 py-3">
                      {isEditing ? (
                        <div className="flex gap-1">
                          {['admin', 'lead', 'tester'].map((role) => (
                            <button
                              key={role}
                              onClick={() => toggleRole(role)}
                              className={`badge text-xs cursor-pointer ${
                                editData.roles?.includes(role) ? ROLE_COLORS[role] : 'bg-gray-100 text-gray-400'
                              }`}
                            >
                              {role}
                            </button>
                          ))}
                        </div>
                      ) : (
                        <div className="flex gap-1">
                          {(u.roles || []).map((role) => (
                            <span key={role} className={`badge text-xs ${ROLE_COLORS[role] || 'badge-gray'}`}>
                              {role}
                            </span>
                          ))}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`badge text-xs ${u.is_active ? 'badge-green' : 'badge-red'}`}>
                        {u.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      {isEditing ? (
                        <div className="flex justify-end gap-2">
                          <button onClick={() => handleEditSave(u.id)} className="btn-primary text-xs px-3 py-1">
                            Save
                          </button>
                          <button onClick={() => setEditingId(null)} className="btn-ghost text-xs px-3 py-1">
                            Cancel
                          </button>
                        </div>
                      ) : (
                        <div className="flex justify-end gap-2">
                          <button
                            onClick={() => handleEditStart(u)}
                            className="text-fg-mid hover:text-fg-teal"
                            title="Edit"
                          >
                            <PencilIcon className="w-4 h-4" />
                          </button>
                          {!isSelf && u.is_active && (
                            <button
                              onClick={() => handleDeactivate(u.id, u.email)}
                              className="text-fg-mid hover:text-red-500"
                              title="Deactivate"
                            >
                              <XMarkIcon className="w-4 h-4" />
                            </button>
                          )}
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Add user modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-md w-full animate-slide-up">
            <div className="p-6">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-lg font-bold text-fg-navy">Add User</h2>
                <button onClick={() => { setShowAddModal(false); setAddError(''); }} className="text-fg-mid hover:text-fg-dark">
                  <XMarkIcon className="w-5 h-5" />
                </button>
              </div>

              {addError && (
                <div className="mb-4 p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">
                  {addError}
                </div>
              )}

              <form onSubmit={handleAdd} className="space-y-4">
                <div>
                  <label className="label">Name</label>
                  <input
                    value={newUser.name}
                    onChange={(e) => setNewUser({ ...newUser, name: e.target.value })}
                    className="input-field"
                    autoFocus
                  />
                </div>
                <div>
                  <label className="label">Email</label>
                  <input
                    type="email"
                    value={newUser.email}
                    onChange={(e) => setNewUser({ ...newUser, email: e.target.value })}
                    className="input-field"
                  />
                </div>
                <div>
                  <label className="label">Password</label>
                  <input
                    type="password"
                    value={newUser.password}
                    onChange={(e) => setNewUser({ ...newUser, password: e.target.value })}
                    className="input-field"
                  />
                </div>
                <div>
                  <label className="label">Roles</label>
                  <div className="flex gap-2">
                    {['admin', 'lead', 'tester'].map((role) => (
                      <button
                        key={role}
                        type="button"
                        onClick={() => {
                          const roles = newUser.roles.includes(role)
                            ? newUser.roles.filter((r) => r !== role)
                            : [...newUser.roles, role];
                          setNewUser({ ...newUser, roles });
                        }}
                        className={`badge text-xs cursor-pointer ${
                          newUser.roles.includes(role) ? ROLE_COLORS[role] : 'bg-gray-100 text-gray-400'
                        }`}
                      >
                        {role}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="flex justify-end gap-3 pt-2">
                  <button type="button" onClick={() => { setShowAddModal(false); setAddError(''); }} className="btn-secondary">
                    Cancel
                  </button>
                  <button type="submit" disabled={adding} className="btn-primary">
                    {adding ? 'Adding...' : 'Add User'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
