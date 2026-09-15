import React, { useEffect, useState } from 'react';
import { apiDownload, apiFetch, isDemoMode } from '../api';
import ReportsTable, { ACTIONS_BY_STATUS, ACTION_DEFS, statusBreakdown } from './ReportsTable';
import CompositionBar from './charts/CompositionBar';

const demoReports = [
  { id: 1, title: 'Q2 Institutional Portfolio Report', client_id: 1, status: 'draft', team: 'Wealth Management', report_type: 'holdings', created_at: null },
  { id: 2, title: 'July Performance Summary', client_id: 1, status: 'review', team: 'Institutional Sales', report_type: 'performance', created_at: null },
  { id: 3, title: 'Investment Committee Factsheet', client_id: 2, status: 'distributed', team: 'Wealth Management', report_type: 'factsheet', created_at: null },
];

const STATUS_PILLS = [
  { value: '', label: 'All' },
  { value: 'draft', label: 'Draft' },
  { value: 'review', label: 'In review' },
  { value: 'compliance', label: 'Compliance' },
  { value: 'approved', label: 'Approved' },
  { value: 'distributed', label: 'Distributed' },
];

export const REPORT_TYPE_LABELS = {
  factsheet: 'Factsheet',
  marketing: 'Marketing Material',
  performance: 'Performance Report',
  holdings: 'Holdings Report',
  pitchbook: 'Pitchbook',
  meeting_pack: 'Meeting Pack',
  custom: 'Custom',
};

export const emptyFilters = { status: '', client_id: '', team: '', report_type: '', asset_class: '', q: '' };

export const buildQuery = (filters) => {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => { if (value) params.set(key, value); });
  const query = params.toString();
  return query ? `?${query}` : '';
};

// Same try/catch-JSON-in-localStorage idiom as Dashboard.js's widget layout --
// a per-viewer convenience, not shared or backend-backed.
const viewsKey = (role) => `lumina_report_views_${role || 'viewer'}`;

const loadViews = (role) => {
  try {
    const raw = window.localStorage.getItem(viewsKey(role));
    if (raw) return JSON.parse(raw);
  } catch { /* corrupt/blocked storage -- fall through to none saved */ }
  return [];
};

const saveViews = (role, views) => {
  try { window.localStorage.setItem(viewsKey(role), JSON.stringify(views)); } catch { /* per-viewer convenience only */ }
};

const Reports = () => {
  const [reports, setReports] = useState([]);
  const [error, setError] = useState('');
  const role = window.localStorage.getItem('lumina_role') || '';
  const canCreate = ['admin', 'editor'].includes(role);

  const [filters, setFilters] = useState(emptyFilters);
  const [searchInput, setSearchInput] = useState('');
  const [facets, setFacets] = useState({ teams: [], reportTypes: [], assetClasses: [] });
  const [clients, setClients] = useState([]);
  const [templates, setTemplates] = useState([]);

  const [form, setForm] = useState({ title: '', client_id: '', team: '', report_type: '', template_id: '' });
  const [formMessage, setFormMessage] = useState('');

  const [savedViews, setSavedViews] = useState(() => loadViews(role));
  const [newViewName, setNewViewName] = useState('');

  const [selectedIds, setSelectedIds] = useState(() => new Set());
  const [bulkMessage, setBulkMessage] = useState('');

  const loadReports = () => {
    if (isDemoMode) { setReports(demoReports); return; }
    apiFetch(`/api/reports${buildQuery(filters)}`).then(setReports).catch(() => setReports(demoReports));
  };

  useEffect(loadReports, [filters]);

  useEffect(() => {
    if (isDemoMode) return;
    apiFetch('/api/reports/facets').then(setFacets).catch(() => {});
    apiFetch('/api/clients').then(setClients).catch(() => {});
    apiFetch('/api/templates').then(setTemplates).catch(() => {});
  }, []);

  useEffect(() => {
    const handle = setTimeout(() => setFilters(current => ({ ...current, q: searchInput })), 300);
    return () => clearTimeout(handle);
  }, [searchInput]);

  const updateFilter = (key, value) => setFilters(current => ({ ...current, [key]: value }));
  const clearFilters = () => { setFilters(emptyFilters); setSearchInput(''); };
  const filtersActive = Object.values(filters).some(Boolean);

  // The selection is a set of report ids -- once the filtered list changes,
  // a previously-selected id may no longer be on screen, so drop the
  // selection rather than let it point at rows the user can't see.
  useEffect(() => { setSelectedIds(new Set()); }, [reports]);

  const applyView = (view) => { setFilters(view.filters); setSearchInput(view.filters.q || ''); };
  const removeView = (viewId) => {
    const next = savedViews.filter(v => v.id !== viewId);
    setSavedViews(next);
    saveViews(role, next);
  };
  const handleSaveView = (event) => {
    event.preventDefault();
    if (!newViewName.trim()) return;
    const next = [...savedViews, { id: Date.now(), name: newViewName.trim(), filters }];
    setSavedViews(next);
    saveViews(role, next);
    setNewViewName('');
  };

  const toggleSelect = (id) => setSelectedIds(current => {
    const next = new Set(current);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });
  const toggleSelectAll = (checked) => setSelectedIds(checked ? new Set(reports.map(r => r.id)) : new Set());

  const selectedReports = reports.filter(r => selectedIds.has(r.id));
  // A bulk action only makes sense when every selected report can legally
  // take it right now -- intersect each selected report's available action
  // names rather than requiring identical status, so a mixed selection still
  // offers whatever they genuinely share.
  const actionNamesFor = (status) => (ACTIONS_BY_STATUS[status] || []).filter(a => a.roles.includes(role)).map(a => a.action);
  const commonActionNames = selectedReports.length === 0 ? [] : selectedReports
    .map(r => actionNamesFor(r.status))
    .reduce((acc, names) => acc.filter(name => names.includes(name)));

  const handleBulkAction = async (action) => {
    setBulkMessage('');
    const results = await Promise.allSettled(
      selectedReports.map(r => apiFetch(`/api/reports/${r.id}/${action}`, { method: 'POST' })),
    );
    const failed = results.filter(r => r.status === 'rejected').length;
    setBulkMessage(
      failed === 0
        ? `${ACTION_DEFS[action]?.label || action} applied to ${results.length} report${results.length === 1 ? '' : 's'}.`
        : `${ACTION_DEFS[action]?.label || action}: ${results.length - failed} succeeded, ${failed} failed.`,
    );
    setTimeout(() => setBulkMessage(''), 5000);
    setSelectedIds(new Set());
    loadReports();
  };

  const handleAction = async (report, action) => {
    setError('');
    try {
      await apiFetch(`/api/reports/${report.id}/${action}`, { method: 'POST' });
      loadReports();
    } catch (requestError) { setError(requestError.message); }
  };

  const handleExport = async (report, format) => {
    setError('');
    const query = format === 'raw' ? 'format=raw&raw_format=json' : `format=${format}`;
    try {
      await apiDownload(`/api/reports/${report.id}/export?${query}`);
    } catch (requestError) { setError(requestError.message); }
  };

  const handleCreate = async (event) => {
    event.preventDefault();
    setFormMessage('');
    try {
      await apiFetch('/api/reports', {
        method: 'POST',
        body: JSON.stringify({
          title: form.title,
          client_id: Number(form.client_id),
          team: form.team || undefined,
          report_type: form.report_type || undefined,
          template_id: form.template_id ? Number(form.template_id) : undefined,
        }),
      });
      setForm({ title: '', client_id: '', team: '', report_type: '', template_id: '' });
      loadReports();
      apiFetch('/api/reports/facets').then(setFacets).catch(() => {});
    } catch (requestError) { setFormMessage(requestError.message); }
  };

  return (
    <div className="reports">
      <div className="page-heading"><div><span className="eyebrow">Production</span><h1>Reports</h1></div>{isDemoMode && <span className="demo-badge">Demo data</span>}</div>

      {canCreate && (
        <section className="panel">
          <h2>New report</h2>
          <form onSubmit={handleCreate}>
            <label>Title
              <input value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} required />
            </label>
            <label>Client
              <select value={form.client_id} onChange={e => setForm({ ...form, client_id: e.target.value })} required>
                <option value="">Choose a client…</option>
                {clients.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </label>
            <label>Team
              <input
                value={form.team} onChange={e => setForm({ ...form, team: e.target.value })}
                list="team-suggestions" placeholder="e.g. Wealth Management"
              />
              <datalist id="team-suggestions">
                {facets.teams.map(team => <option key={team} value={team} />)}
              </datalist>
            </label>
            <label>Report type
              <select value={form.report_type} onChange={e => setForm({ ...form, report_type: e.target.value })}>
                <option value="">Not specified</option>
                {Object.entries(REPORT_TYPE_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </label>
            <label>Template (optional — leave blank for a plain PDF)
              <select value={form.template_id} onChange={e => setForm({ ...form, template_id: e.target.value })}>
                <option value="">No template</option>
                {templates.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
            </label>
            <div className="form-actions">
              <button type="submit">Create report</button>
            </div>
          </form>
          {formMessage && <p className="form-message">{formMessage}</p>}
        </section>
      )}

      {reports.length > 0 && (
        <section className="panel">
          <div className="panel-header"><h2>Status mix</h2></div>
          <CompositionBar title="Status mix" data={statusBreakdown(reports)} />
        </section>
      )}

      <section className="panel">
        <div className="saved-views-row">
          {savedViews.map(view => (
            <span key={view.id} className="saved-view-chip">
              <button type="button" onClick={() => applyView(view)}>{view.name}</button>
              <button type="button" className="saved-view-remove" aria-label={`Remove view ${view.name}`} onClick={() => removeView(view.id)}>×</button>
            </span>
          ))}
          {filtersActive && (
            <form className="saved-view-form" onSubmit={handleSaveView}>
              <input
                type="text" placeholder="Save current filters as…"
                value={newViewName} onChange={e => setNewViewName(e.target.value)}
              />
              <button type="submit" disabled={!newViewName.trim()}>Save view</button>
            </form>
          )}
        </div>
        <div className="filter-bar">
          <div className="filter-pills">
            {STATUS_PILLS.map(pill => (
              <button
                key={pill.value} type="button"
                className={`filter-pill ${filters.status === pill.value ? 'active' : ''}`}
                onClick={() => updateFilter('status', pill.value)}
              >
                {pill.label}
              </button>
            ))}
          </div>
          <select className="filter-select" value={filters.client_id} onChange={e => updateFilter('client_id', e.target.value)}>
            <option value="">All clients</option>
            {clients.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <select className="filter-select" value={filters.team} onChange={e => updateFilter('team', e.target.value)}>
            <option value="">All teams</option>
            {facets.teams.map(team => <option key={team} value={team}>{team}</option>)}
          </select>
          <select className="filter-select" value={filters.report_type} onChange={e => updateFilter('report_type', e.target.value)}>
            <option value="">All types</option>
            {facets.reportTypes.map(type => <option key={type} value={type}>{REPORT_TYPE_LABELS[type] || type}</option>)}
          </select>
          <select className="filter-select" value={filters.asset_class} onChange={e => updateFilter('asset_class', e.target.value)}>
            <option value="">All asset classes</option>
            {facets.assetClasses.map(assetClass => <option key={assetClass} value={assetClass}>{assetClass}</option>)}
          </select>
          <input
            className="filter-search" type="search" placeholder="Search title…"
            value={searchInput} onChange={e => setSearchInput(e.target.value)}
          />
          {filtersActive && <button type="button" className="filter-clear" onClick={clearFilters}>Clear filters</button>}
        </div>

        {selectedIds.size > 0 && (
          <div className="bulk-action-bar">
            <span>{selectedIds.size} selected</span>
            {commonActionNames.length > 0 ? (
              commonActionNames.map(action => (
                <button
                  key={action} type="button"
                  className={ACTION_DEFS[action]?.tone && ACTION_DEFS[action].tone !== 'neutral' ? `action-btn tone-${ACTION_DEFS[action].tone}` : undefined}
                  onClick={() => handleBulkAction(action)}
                >
                  {ACTION_DEFS[action]?.label || action}
                </button>
              ))
            ) : (
              <span className="bulk-action-none">No action is available to every selected report.</span>
            )}
            <button type="button" className="filter-clear" onClick={() => setSelectedIds(new Set())}>Clear selection</button>
          </div>
        )}
        {bulkMessage && <p className="form-message form-message-success">{bulkMessage}</p>}

        <ReportsTable
          reports={reports} role={role} onAction={handleAction} onExport={handleExport}
          selectable selectedIds={selectedIds} onToggleSelect={toggleSelect} onToggleSelectAll={toggleSelectAll}
        />
      </section>
      {error && <p className="form-message">{error}</p>}
    </div>
  );
};

export default Reports;
