import React, { useEffect, useState } from 'react';
import { apiFetch, isDemoMode } from '../api';

const emptyForm = { title: '', body: '', category: '' };

const Disclosures = () => {
  const [disclosures, setDisclosures] = useState([]);
  const [error, setError] = useState('');
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(emptyForm);

  const loadDisclosures = () => {
    if (isDemoMode) return;
    apiFetch('/api/disclosures').then(setDisclosures).catch(requestError => setError(requestError.message));
  };

  useEffect(() => { if (!isDemoMode) loadDisclosures(); }, []);

  const resetForm = () => { setEditingId(null); setForm(emptyForm); };

  const startEdit = (disclosure) => {
    setEditingId(disclosure.id);
    setForm({ title: disclosure.title, body: disclosure.body, category: disclosure.category || '' });
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    const payload = { title: form.title, body: form.body, category: form.category || undefined };
    try {
      if (editingId) {
        await apiFetch(`/api/disclosures/${editingId}`, { method: 'PUT', body: JSON.stringify(payload) });
      } else {
        await apiFetch('/api/disclosures', { method: 'POST', body: JSON.stringify(payload) });
      }
      resetForm();
      loadDisclosures();
    } catch (requestError) { setError(requestError.message); }
  };

  const handleDelete = async (disclosureId) => {
    setError('');
    try {
      await apiFetch(`/api/disclosures/${disclosureId}`, { method: 'DELETE' });
      loadDisclosures();
    } catch (requestError) { setError(requestError.message); }
  };

  return (
    <div className="disclosures">
      <div className="page-heading">
        <div><span className="eyebrow">Compliance</span><h1>Disclosures</h1></div>
        {isDemoMode && <span className="demo-badge">Demo data</span>}
      </div>
      <p className="panel-subtitle">
        A governed library of reusable legal and footnote language. Attach these to a template from the template
        editor rather than retyping disclosure text per document.
      </p>

      <section className="panel">
        <h2>Library</h2>
        <ul className="report-list">
          {disclosures.map(disclosure => (
            <li key={disclosure.id}>
              <span>{disclosure.title}{disclosure.category && <span className="reports-table-subtext"> · {disclosure.category}</span>}</span>
              <button type="button" onClick={() => startEdit(disclosure)}>Edit</button>
              <button type="button" onClick={() => handleDelete(disclosure.id)}>Delete</button>
            </li>
          ))}
          {disclosures.length === 0 && <li>No disclosures yet.</li>}
        </ul>
      </section>

      <section className="panel">
        <h2>{editingId ? 'Edit disclosure' : 'New disclosure'}</h2>
        <form onSubmit={handleSubmit}>
          <label>Title
            <input value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} required />
          </label>
          <label>Category
            <input
              placeholder="e.g. General Risk, Foreign Securities, Small-Cap"
              value={form.category} onChange={e => setForm({ ...form, category: e.target.value })}
            />
          </label>
          <label>Body
            <textarea
              placeholder="Full disclosure text as it should appear in the document"
              value={form.body} onChange={e => setForm({ ...form, body: e.target.value })} required
            />
          </label>
          <div className="form-actions">
            <button type="submit">{editingId ? 'Save changes' : 'Create disclosure'}</button>
            {editingId && <button type="button" onClick={resetForm}>Cancel</button>}
          </div>
        </form>
      </section>

      {error && <p className="form-message">{error}</p>}
    </div>
  );
};

export default Disclosures;
