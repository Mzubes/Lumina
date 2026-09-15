import React, { useEffect, useState } from 'react';
import { apiFetch, isDemoMode } from '../api';

const ROLES = [
  { value: 'admin', label: 'Admin' },
  { value: 'editor', label: 'Editor' },
  { value: 'viewer', label: 'Viewer' },
  { value: 'compliance', label: 'Compliance' },
  { value: 'client', label: 'Client' },
];

const emptyForm = { email: '', role: 'viewer', client_id: '', password: '' };

const demoUsers = [
  { id: 1, email: 'admin@lumina.test', role: 'admin', client_id: null },
  { id: 2, email: 'editor@lumina.test', role: 'editor', client_id: null },
  { id: 3, email: 'compliance@lumina.test', role: 'compliance', client_id: null },
  { id: 4, email: 'client@lumina.test', role: 'client', client_id: 1 },
];

const Users = () => {
  const [users, setUsers] = useState([]);
  const [clients, setClients] = useState([]);
  const [error, setError] = useState('');
  const [flash, setFlash] = useState('');

  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(emptyForm);

  const loadUsers = () => {
    if (isDemoMode) { setUsers(demoUsers); return; }
    apiFetch('/api/users').then(setUsers).catch(requestError => setError(requestError.message));
  };

  useEffect(() => {
    if (isDemoMode) return;
    loadUsers();
    apiFetch('/api/clients').then(setClients).catch(() => {});
  }, []);

  const resetForm = () => { setEditingId(null); setForm(emptyForm); };
  const startEdit = (user) => {
    setEditingId(user.id);
    setForm({ email: user.email, role: user.role, client_id: user.client_id || '', password: '' });
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    const payload = {
      email: form.email, role: form.role,
      client_id: form.role === 'client' ? Number(form.client_id) || null : null,
    };
    if (form.password) payload.password = form.password;
    try {
      if (editingId) {
        await apiFetch(`/api/users/${editingId}`, { method: 'PUT', body: JSON.stringify(payload) });
        setFlash('User updated.');
      } else {
        if (!form.password) { setError('password is required'); return; }
        await apiFetch('/api/users', { method: 'POST', body: JSON.stringify(payload) });
        setFlash('User created.');
      }
      setTimeout(() => setFlash(''), 4000);
      resetForm();
      loadUsers();
    } catch (requestError) { setError(requestError.message); }
  };

  const handleDelete = async (userId) => {
    setError('');
    try {
      await apiFetch(`/api/users/${userId}`, { method: 'DELETE' });
      loadUsers();
    } catch (requestError) { setError(requestError.message); }
  };

  const clientName = (clientId) => (clients.find(c => c.id === clientId)?.name || `Client #${clientId}`);

  return (
    <div className="users-admin">
      <div className="page-heading">
        <div><span className="eyebrow">Admin</span><h1>Users &amp; Roles</h1></div>
        {isDemoMode && <span className="demo-badge">Demo data</span>}
      </div>

      <section className="panel">
        <h2>Users</h2>
        <ul className="report-list">
          {users.map(user => (
            <li key={user.id}>
              <span>
                {user.email}
                <span className="reports-table-subtext">
                  {' · '}{ROLES.find(r => r.value === user.role)?.label || user.role}
                  {user.role === 'client' && user.client_id ? ` · ${clientName(user.client_id)}` : ''}
                </span>
              </span>
              <button type="button" onClick={() => startEdit(user)}>Edit</button>
              <button type="button" onClick={() => handleDelete(user.id)}>Delete</button>
            </li>
          ))}
          {users.length === 0 && <li>No users yet.</li>}
        </ul>
      </section>

      <section className="panel">
        <h2>{editingId ? 'Edit user' : 'New user'}</h2>
        <form onSubmit={handleSubmit}>
          <label>Email
            <input type="email" value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} required />
          </label>
          <label>Role
            <select value={form.role} onChange={e => setForm({ ...form, role: e.target.value })}>
              {ROLES.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
            </select>
          </label>
          {form.role === 'client' && (
            <label>Client
              <select value={form.client_id} onChange={e => setForm({ ...form, client_id: e.target.value })} required>
                <option value="">Select a client…</option>
                {clients.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </label>
          )}
          <label>{editingId ? 'Reset password (leave blank to keep current)' : 'Password'}
            <input
              type="password" value={form.password} onChange={e => setForm({ ...form, password: e.target.value })}
              required={!editingId} placeholder={editingId ? '••••••••' : ''}
            />
          </label>
          <div className="form-actions">
            <button type="submit">{editingId ? 'Save changes' : 'Create user'}</button>
            {editingId && <button type="button" onClick={resetForm}>Cancel</button>}
          </div>
        </form>
      </section>

      {flash && <p className="form-message form-message-success">✓ {flash}</p>}
      {error && <p className="form-message">{error}</p>}
    </div>
  );
};

export default Users;
