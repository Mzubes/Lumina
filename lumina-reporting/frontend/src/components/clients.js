import React, { useEffect, useState } from 'react';
import { apiFetch, isDemoMode } from '../api';

const emptyClientForm = { name: '', contact_email: '' };
const emptyContactForm = { name: '', email: '', title: '', phone: '' };

const Clients = () => {
  const [clients, setClients] = useState([]);
  const [error, setError] = useState('');

  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(emptyClientForm);

  const [expandedClientId, setExpandedClientId] = useState(null);
  const [contactsByClient, setContactsByClient] = useState({});
  const [contactForm, setContactForm] = useState(emptyContactForm);
  const [editingContactId, setEditingContactId] = useState(null);

  const loadClients = () => {
    if (isDemoMode) return;
    apiFetch('/api/clients').then(setClients).catch(requestError => setError(requestError.message));
  };

  useEffect(() => { if (!isDemoMode) loadClients(); }, []);

  const resetForm = () => { setEditingId(null); setForm(emptyClientForm); };
  const startEdit = (client) => { setEditingId(client.id); setForm({ name: client.name, contact_email: client.contact_email || '' }); };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    const payload = { name: form.name, contact_email: form.contact_email || undefined };
    try {
      if (editingId) {
        await apiFetch(`/api/clients/${editingId}`, { method: 'PUT', body: JSON.stringify(payload) });
      } else {
        await apiFetch('/api/clients', { method: 'POST', body: JSON.stringify(payload) });
      }
      resetForm();
      loadClients();
    } catch (requestError) { setError(requestError.message); }
  };

  const handleDelete = async (clientId) => {
    setError('');
    try {
      await apiFetch(`/api/clients/${clientId}`, { method: 'DELETE' });
      loadClients();
    } catch (requestError) { setError(requestError.message); }
  };

  const loadContacts = (clientId) => {
    apiFetch(`/api/clients/${clientId}/contacts`)
      .then(contacts => setContactsByClient(current => ({ ...current, [clientId]: contacts })))
      .catch(requestError => setError(requestError.message));
  };

  const toggleExpanded = (clientId) => {
    const next = expandedClientId === clientId ? null : clientId;
    setExpandedClientId(next);
    setEditingContactId(null);
    setContactForm(emptyContactForm);
    if (next && !contactsByClient[next]) loadContacts(next);
  };

  const startEditContact = (contact) => {
    setEditingContactId(contact.id);
    setContactForm({ name: contact.name, email: contact.email || '', title: contact.title || '', phone: contact.phone || '' });
  };

  const handleContactSubmit = async (event, clientId) => {
    event.preventDefault();
    setError('');
    const payload = {
      name: contactForm.name, email: contactForm.email || undefined,
      title: contactForm.title || undefined, phone: contactForm.phone || undefined,
    };
    try {
      if (editingContactId) {
        await apiFetch(`/api/clients/${clientId}/contacts/${editingContactId}`, { method: 'PUT', body: JSON.stringify(payload) });
      } else {
        await apiFetch(`/api/clients/${clientId}/contacts`, { method: 'POST', body: JSON.stringify(payload) });
      }
      setEditingContactId(null);
      setContactForm(emptyContactForm);
      loadContacts(clientId);
    } catch (requestError) { setError(requestError.message); }
  };

  const handleContactDelete = async (clientId, contactId) => {
    setError('');
    try {
      await apiFetch(`/api/clients/${clientId}/contacts/${contactId}`, { method: 'DELETE' });
      loadContacts(clientId);
    } catch (requestError) { setError(requestError.message); }
  };

  return (
    <div className="clients-admin">
      <div className="page-heading">
        <div><span className="eyebrow">Admin</span><h1>Clients &amp; Contacts</h1></div>
        {isDemoMode && <span className="demo-badge">Demo data</span>}
      </div>

      <section className="panel">
        <h2>Clients</h2>
        <ul className="report-list client-list">
          {clients.map(client => (
            <li key={client.id} className="client-list-item">
              <div className="client-list-row">
                <button type="button" className="client-expand" onClick={() => toggleExpanded(client.id)}>
                  {expandedClientId === client.id ? '▾' : '▸'} {client.name}
                  {client.contact_email && <span className="reports-table-subtext"> · {client.contact_email}</span>}
                </button>
                <button type="button" onClick={() => startEdit(client)}>Edit</button>
                <button type="button" onClick={() => handleDelete(client.id)}>Delete</button>
              </div>

              {expandedClientId === client.id && (
                <div className="client-contacts">
                  <ul className="report-list">
                    {(contactsByClient[client.id] || []).map(contact => (
                      <li key={contact.id}>
                        <span>
                          {contact.name}
                          {(contact.title || contact.email) && (
                            <span className="reports-table-subtext"> · {[contact.title, contact.email].filter(Boolean).join(' · ')}</span>
                          )}
                        </span>
                        <button type="button" onClick={() => startEditContact(contact)}>Edit</button>
                        <button type="button" onClick={() => handleContactDelete(client.id, contact.id)}>Delete</button>
                      </li>
                    ))}
                    {(contactsByClient[client.id] || []).length === 0 && <li>No contacts yet.</li>}
                  </ul>
                  <form className="contact-form" onSubmit={e => handleContactSubmit(e, client.id)}>
                    <input placeholder="Name" value={contactForm.name} onChange={e => setContactForm({ ...contactForm, name: e.target.value })} required />
                    <input placeholder="Title" value={contactForm.title} onChange={e => setContactForm({ ...contactForm, title: e.target.value })} />
                    <input placeholder="Email" value={contactForm.email} onChange={e => setContactForm({ ...contactForm, email: e.target.value })} />
                    <input placeholder="Phone" value={contactForm.phone} onChange={e => setContactForm({ ...contactForm, phone: e.target.value })} />
                    <button type="submit">{editingContactId ? 'Save contact' : 'Add contact'}</button>
                    {editingContactId && (
                      <button type="button" onClick={() => { setEditingContactId(null); setContactForm(emptyContactForm); }}>Cancel</button>
                    )}
                  </form>
                </div>
              )}
            </li>
          ))}
          {clients.length === 0 && <li>No clients yet.</li>}
        </ul>
      </section>

      <section className="panel">
        <h2>{editingId ? 'Edit client' : 'New client'}</h2>
        <form onSubmit={handleSubmit}>
          <label>Name
            <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} required />
          </label>
          <label>Primary contact email
            <input type="email" value={form.contact_email} onChange={e => setForm({ ...form, contact_email: e.target.value })} />
          </label>
          <div className="form-actions">
            <button type="submit">{editingId ? 'Save changes' : 'Create client'}</button>
            {editingId && <button type="button" onClick={resetForm}>Cancel</button>}
          </div>
        </form>
      </section>

      {error && <p className="form-message">{error}</p>}
    </div>
  );
};

export default Clients;
