import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiFetch, isDemoMode } from '../api';

const matches = (text, query) => (text || '').toLowerCase().includes(query);

// Reports have a real per-item route; Clients/Templates don't today, so
// their results link to the list page instead of a specific record --
// flagged inline in the result copy rather than hidden.
const GlobalSearch = ({ open, onClose }) => {
  const navigate = useNavigate();
  const inputRef = useRef(null);
  const [query, setQuery] = useState('');
  const [reports, setReports] = useState([]);
  const [clients, setClients] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!open) return;
    setQuery('');
    setTimeout(() => inputRef.current?.focus(), 0);
    if (isDemoMode || loaded) return;
    Promise.all([
      apiFetch('/api/reports').catch(() => []),
      apiFetch('/api/clients').catch(() => []),
      apiFetch('/api/templates').catch(() => []),
    ]).then(([reportData, clientData, templateData]) => {
      setReports(reportData);
      setClients(clientData);
      setTemplates(templateData);
      setLoaded(true);
    });
  }, [open, loaded]);

  useEffect(() => {
    if (!open) return undefined;
    const handleKeyDown = (event) => { if (event.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [open, onClose]);

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return { reports: [], clients: [], templates: [] };
    return {
      reports: reports.filter(r => matches(r.title, q)).slice(0, 8),
      clients: clients.filter(c => matches(c.name, q)).slice(0, 8),
      templates: templates.filter(t => matches(t.name, q)).slice(0, 8),
    };
  }, [query, reports, clients, templates]);

  if (!open) return null;

  const goTo = (path) => { onClose(); navigate(path); };
  const hasResults = results.reports.length || results.clients.length || results.templates.length;

  return (
    <div className="global-search-overlay" onClick={onClose}>
      <div className="global-search-panel" onClick={event => event.stopPropagation()}>
        <input
          ref={inputRef}
          className="global-search-input"
          type="text"
          placeholder="Search reports, clients, templates…"
          value={query}
          onChange={e => setQuery(e.target.value)}
        />
        <div className="global-search-results">
          {!query.trim() && <p className="global-search-hint">Start typing to search across the firm.</p>}
          {query.trim() && !hasResults && <p className="global-search-hint">No matches for "{query}".</p>}

          {results.reports.length > 0 && (
            <div className="global-search-group">
              <div className="global-search-group-label">Reports</div>
              {results.reports.map(report => (
                <button key={`report-${report.id}`} type="button" className="global-search-result" onClick={() => goTo(`/reports/${report.id}`)}>
                  {report.title}
                </button>
              ))}
            </div>
          )}

          {results.clients.length > 0 && (
            <div className="global-search-group">
              <div className="global-search-group-label">Clients</div>
              {results.clients.map(clientItem => (
                <button key={`client-${clientItem.id}`} type="button" className="global-search-result" onClick={() => goTo('/clients')}>
                  {clientItem.name}
                  <span className="global-search-result-hint">Open Clients &amp; Contacts</span>
                </button>
              ))}
            </div>
          )}

          {results.templates.length > 0 && (
            <div className="global-search-group">
              <div className="global-search-group-label">Templates</div>
              {results.templates.map(template => (
                <button key={`template-${template.id}`} type="button" className="global-search-result" onClick={() => goTo('/templates')}>
                  {template.name}
                  <span className="global-search-result-hint">Open Templates</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default GlobalSearch;
