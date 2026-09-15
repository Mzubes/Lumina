import React, { useEffect, useState } from 'react';
import { apiFetch, isDemoMode } from '../api';

const emptyForm = { name: '', description: '' };

const demoGroups = [
  { id: 1, name: 'Compliance', description: 'Final regulatory sign-off', color: 'cat-1', member_count: 2 },
  { id: 2, name: 'Client Reporting', description: 'Prepares and QCs client-facing output', color: 'cat-2', member_count: 4 },
  { id: 3, name: 'Portfolio Managers', description: '', color: 'cat-3', member_count: 3 },
];

const WorkflowGroups = () => {
  const [groups, setGroups] = useState([]);
  const [users, setUsers] = useState([]);
  const [error, setError] = useState('');

  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(emptyForm);

  const [expandedGroupId, setExpandedGroupId] = useState(null);
  const [membersByGroup, setMembersByGroup] = useState({});
  const [newMemberId, setNewMemberId] = useState('');

  const loadGroups = () => {
    if (isDemoMode) { setGroups(demoGroups); return; }
    apiFetch('/api/workflow-groups').then(setGroups).catch(requestError => setError(requestError.message));
  };

  useEffect(() => {
    if (isDemoMode) return;
    loadGroups();
    apiFetch('/api/users').then(setUsers).catch(() => {});
  }, []);

  const resetForm = () => { setEditingId(null); setForm(emptyForm); };
  const startEdit = (group) => { setEditingId(group.id); setForm({ name: group.name, description: group.description || '' }); };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    const payload = { name: form.name, description: form.description || undefined };
    try {
      if (editingId) {
        await apiFetch(`/api/workflow-groups/${editingId}`, { method: 'PUT', body: JSON.stringify(payload) });
      } else {
        await apiFetch('/api/workflow-groups', { method: 'POST', body: JSON.stringify(payload) });
      }
      resetForm();
      loadGroups();
    } catch (requestError) { setError(requestError.message); }
  };

  const handleDelete = async (groupId) => {
    setError('');
    try {
      await apiFetch(`/api/workflow-groups/${groupId}`, { method: 'DELETE' });
      loadGroups();
    } catch (requestError) { setError(requestError.message); }
  };

  const loadMembers = (groupId) => {
    apiFetch(`/api/workflow-groups/${groupId}/members`)
      .then(members => setMembersByGroup(current => ({ ...current, [groupId]: members })))
      .catch(requestError => setError(requestError.message));
  };

  const toggleExpanded = (groupId) => {
    const next = expandedGroupId === groupId ? null : groupId;
    setExpandedGroupId(next);
    setNewMemberId('');
    if (next && !membersByGroup[next]) loadMembers(next);
  };

  const handleAddMember = async (event, groupId) => {
    event.preventDefault();
    if (!newMemberId) return;
    setError('');
    try {
      await apiFetch(`/api/workflow-groups/${groupId}/members`, {
        method: 'POST', body: JSON.stringify({ user_id: Number(newMemberId) }),
      });
      setNewMemberId('');
      loadMembers(groupId);
      loadGroups();
    } catch (requestError) { setError(requestError.message); }
  };

  const handleRemoveMember = async (groupId, userId) => {
    setError('');
    try {
      await apiFetch(`/api/workflow-groups/${groupId}/members/${userId}`, { method: 'DELETE' });
      loadMembers(groupId);
      loadGroups();
    } catch (requestError) { setError(requestError.message); }
  };

  const memberIdsFor = (groupId) => new Set((membersByGroup[groupId] || []).map(m => m.id));

  return (
    <div className="workflow-groups-admin">
      <div className="page-heading">
        <div><span className="eyebrow">Admin</span><h1>Workflow Groups</h1></div>
        {isDemoMode && <span className="demo-badge">Demo data</span>}
      </div>
      <p className="panel-subtitle">
        The teams that carry out production work -- Compliance, Client Reporting, Portfolio Managers, or whatever
        your firm calls them. Assign a group to a step when building a template's workflow diagram, then add the
        people who do that work here.
      </p>

      <section className="panel">
        <h2>Groups</h2>
        <ul className="report-list client-list">
          {groups.map(group => (
            <li key={group.id} className="client-list-item">
              <div className="client-list-row">
                <button type="button" className="client-expand" onClick={() => toggleExpanded(group.id)}>
                  {expandedGroupId === group.id ? '▾' : '▸'}
                  <span className={`workflow-group-swatch swatch-${group.color}`} />
                  {group.name}
                  <span className="reports-table-subtext">
                    {' · '}{group.member_count} member{group.member_count === 1 ? '' : 's'}
                    {group.description ? ` · ${group.description}` : ''}
                  </span>
                </button>
                <button type="button" onClick={() => startEdit(group)}>Edit</button>
                <button type="button" onClick={() => handleDelete(group.id)}>Delete</button>
              </div>

              {expandedGroupId === group.id && (
                <div className="client-contacts">
                  <ul className="report-list">
                    {(membersByGroup[group.id] || []).map(member => (
                      <li key={member.id}>
                        <span>{member.email}</span>
                        <button type="button" onClick={() => handleRemoveMember(group.id, member.id)}>Remove</button>
                      </li>
                    ))}
                    {(membersByGroup[group.id] || []).length === 0 && <li>No members yet.</li>}
                  </ul>
                  <form className="contact-form" onSubmit={e => handleAddMember(e, group.id)}>
                    <select value={newMemberId} onChange={e => setNewMemberId(e.target.value)}>
                      <option value="">Add a member…</option>
                      {users.filter(u => !memberIdsFor(group.id).has(u.id)).map(u => (
                        <option key={u.id} value={u.id}>{u.email}</option>
                      ))}
                    </select>
                    <button type="submit" disabled={!newMemberId}>Add</button>
                  </form>
                </div>
              )}
            </li>
          ))}
          {groups.length === 0 && <li>No workflow groups yet.</li>}
        </ul>
      </section>

      <section className="panel">
        <h2>{editingId ? 'Edit group' : 'New group'}</h2>
        <form onSubmit={handleSubmit}>
          <label>Name
            <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="e.g. Compliance" required />
          </label>
          <label>Description (optional)
            <input value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} />
          </label>
          <div className="form-actions">
            <button type="submit">{editingId ? 'Save changes' : 'Create group'}</button>
            {editingId && <button type="button" onClick={resetForm}>Cancel</button>}
          </div>
        </form>
      </section>

      {error && <p className="form-message">{error}</p>}
    </div>
  );
};

export default WorkflowGroups;
