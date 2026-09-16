import React, { useEffect, useState } from 'react';
import { apiFetch } from '../api';

const formatDate = (value) => (value ? new Date(value).toLocaleString() : '—');

const publicUrlFor = (token) => `${window.location.origin}${window.location.pathname}#/public/${token}`;

const DistributionPanel = ({ reportId, clientId, role }) => {
  const canManage = role === 'admin' || role === 'editor';

  const [links, setLinks] = useState([]);
  const [contacts, setContacts] = useState([]);
  const [contactId, setContactId] = useState('');
  const [error, setError] = useState('');
  const [copiedId, setCopiedId] = useState(null);

  const loadLinks = () => {
    apiFetch(`/api/reports/${reportId}/distribution-links`).then(setLinks).catch(() => {});
  };

  useEffect(loadLinks, [reportId]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!clientId) { setContacts([]); return; }
    apiFetch(`/api/clients/${clientId}/contacts`).then(setContacts).catch(() => setContacts([]));
  }, [clientId]);

  const handleCreate = async () => {
    setError('');
    try {
      const link = await apiFetch(`/api/reports/${reportId}/distribution-links`, {
        method: 'POST', body: JSON.stringify({ contact_id: contactId ? Number(contactId) : null }),
      });
      setLinks(current => [link, ...current]);
      setContactId('');
    } catch (requestError) { setError(requestError.message); }
  };

  const handleRevoke = async (linkId) => {
    setError('');
    try {
      const updated = await apiFetch(`/api/reports/${reportId}/distribution-links/${linkId}/revoke`, { method: 'POST' });
      setLinks(current => current.map(link => (link.id === linkId ? updated : link)));
    } catch (requestError) { setError(requestError.message); }
  };

  const handleCopy = async (link) => {
    const url = publicUrlFor(link.token);
    try {
      await navigator.clipboard.writeText(url);
      setCopiedId(link.id);
      setTimeout(() => setCopiedId(null), 2000);
    } catch {
      window.prompt('Copy this link:', url); // eslint-disable-line no-alert
    }
  };

  return (
    <section className="panel">
      <div className="panel-header"><h2>Distribution</h2></div>
      <p className="panel-subtitle">
        Anyone with a link below can view and export this report without signing in.
      </p>

      {error && <p className="form-message">{error}</p>}

      {canManage && (
        <div className="distribution-create-row">
          <select value={contactId} onChange={(event) => setContactId(event.target.value)}>
            <option value="">Anonymous link (no contact)</option>
            {contacts.map(contact => (
              <option key={contact.id} value={contact.id}>{contact.name}{contact.title ? ` — ${contact.title}` : ''}</option>
            ))}
          </select>
          <button type="button" onClick={handleCreate}>Generate link</button>
        </div>
      )}

      <ul className="distribution-link-list">
        {links.map(link => {
          const contact = contacts.find(c => c.id === link.contact_id);
          return (
            <li className="distribution-link-item" key={link.id}>
              <div className="distribution-link-main">
                <code className="distribution-link-url">{publicUrlFor(link.token)}</code>
                <div className="distribution-link-meta">
                  {contact ? contact.name : 'Anonymous link'} · Created {formatDate(link.created_at)}
                  {link.revoked_at && <span className="distribution-link-revoked"> · Revoked {formatDate(link.revoked_at)}</span>}
                </div>
              </div>
              <div className="distribution-link-actions">
                <button type="button" onClick={() => handleCopy(link)}>{copiedId === link.id ? 'Copied' : 'Copy'}</button>
                {canManage && !link.revoked_at && (
                  <button type="button" className="action-btn tone-negative" onClick={() => handleRevoke(link.id)}>Revoke</button>
                )}
              </div>
            </li>
          );
        })}
        {links.length === 0 && <li className="timeline-empty">No share links yet.</li>}
      </ul>
    </section>
  );
};

export default DistributionPanel;
