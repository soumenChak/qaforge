import React, { useState, useEffect, useCallback } from 'react';
import { usersAPI, authAPI } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { PlusIcon, XMarkIcon, PencilIcon, UsersIcon, KeyIcon } from '@heroicons/react/24/outline';
import Spinner from '../components/Spinner';

const ROLE_COLORS = {
  admin: 'bg-red-100 text-red-700',
  engineer: 'bg-blue-100 text-blue-700',
};

export default function Users() {
  const { user: currentUser, isAdmin } = useAuth();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [editData, setEditData] = useState({});

  // Add user form
  const [newUser, setNewUser] = useState({ name: '', email: '', password: '', roles: ['engineer'] });
  const [addError, setAddError] = useState('');
  const [adding, setAdding] = useState(false);

  // Change password
  const [showPwdForm, setShowPwdForm] = useState(false);
  const [pwdData, setPwdData] = useState({ current_password: '', new_password: '', confirm: '' });
  const [pwdError, setPwdError] = useState('');
  const [pwdSuccess, setPwdSuccess] = useState('');
  const [changingPwd, setChangingPwd] = useState(false);

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
      setNewUser({ name: '', email: '', password: '', roles: ['engineer'] });
      loadUsers();
    } catch (err) {
      setAddError(err.response?.data?.detail || 'Failed to add user.');
    } finally {
      setAdding(false);
    }
  };

  const handleEditStart = (u) => {
    setEditingId(u.id);
    setEditData({ name: u.name, roles: u.roles || ['engineer'] });
  };

  const handleEditSave = async (userId) => {
    try {
      await usersAPI.update(userId, editData);
      setEditingId(null);
      loadUsers();
    } catch (err) {
      { const d = err.response?.data?.detail; alert(typeof d === 'string' ? d : (err.message || 'Failed to update user.')); }
    }
  };

  const handleDeactivate = async (userId, email) => {
    if (!window.confirm(`Deactivate user ${email}?`)) return;
    try {
      await usersAPI.delete(userId);
      loadUsers();
    } catch (err) {
      { const d = err.response?.data?.detail; alert(typeof d === 'string' ? d : (err.message || 'Failed to deactivate user.')); }
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

  const handleChangePassword = async (e) => {
    e.preventDefault();
    setPwdError('');
    setPwdSuccess('');
    if (pwdData.new_password.length < 6) {
      setPwdError('New password must be at least 6 characters.');
      return;
    }
    if (pwdData.new_password !== pwdData.confirm) {
      setPwdError('Passwords do not match.');
      return;
    }
    setChangingPwd(true);
    try {
      await usersAPI.changePassword({
        current_password: pwdData.current_password,
        new_password: pwdData.new_password,
      });
      setPwdSuccess('Password changed successfully!');
      setPwdData({ current_password: '', new_password: '', confirm: '' });
      setTimeout(() => setPwdSuccess(''), 5000);
    } catch (err) {
      setPwdError(err.response?.data?.detail || 'Failed to change password.');
    } finally {
      setChangingPwd(false);
    }
  };

  // Password change section — available to ALL users
  const passwordSection = (
    <div className="card-static mt-6">
      <div className="h-1 bg-gradient-to-r from-amber-400 to-orange-400" />
      <div className="p-6">
        <button
          onClick={() => { setShowPwdForm(!showPwdForm); setPwdError(''); setPwdSuccess(''); }}
          className="flex items-center gap-2 text-fg-navy font-semibold hover:text-fg-teal transition-colors"
        >
          <KeyIcon className="w-5 h-5" />
          Change Password
          <span className="text-xs text-fg-mid ml-2">{showPwdForm ? '(hide)' : '(click to expand)'}</span>
        </button>

        {showPwdForm && (
          <form onSubmit={handleChangePassword} className="mt-4 max-w-sm space-y-3">
            {pwdError && (
              <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">{pwdError}</div>
            )}
            {pwdSuccess && (
              <div className="p-3 rounded-lg bg-green-50 border border-green-200 text-sm text-green-700">{pwdSuccess}</div>
            )}
            <div>
              <label className="label">Current Password</label>
              <input
                type="password"
                value={pwdData.current_password}
                onChange={(e) => setPwdData({ ...pwdData, current_password: e.target.value })}
                className="input-field"
                required
              />
            </div>
            <div>
              <label className="label">New Password</label>
              <input
                type="password"
                value={pwdData.new_password}
                onChange={(e) => setPwdData({ ...pwdData, new_password: e.target.value })}
                className="input-field"
                required
              />
            </div>
            <div>
              <label className="label">Confirm New Password</label>
              <input
                type="password"
                value={pwdData.confirm}
                onChange={(e) => setPwdData({ ...pwdData, confirm: e.target.value })}
                className="input-field"
                required
              />
            </div>
            <button type="submit" disabled={changingPwd} className="btn-primary text-sm">
              {changingPwd ? 'Changing...' : 'Update Password'}
            </button>
          </form>
        )}
      </div>
    </div>
  );

  if (!isAdmin) {
    return (
      <div className="page-container">
        <div className="section-header">
          <h1 className="text-2xl font-bold text-fg-navy">My Account</h1>
        </div>
        {passwordSection}
      </div>
    );
  }

  if (loading) {
    return (
      <div className="page-container">
        <Spinner />
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
          Add Engineer
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
                          {['admin', 'engineer'].map((role) => (
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

      {/* Change password (for current user) */}
      {passwordSection}

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
                    {['admin', 'engineer'].map((role) => (
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
