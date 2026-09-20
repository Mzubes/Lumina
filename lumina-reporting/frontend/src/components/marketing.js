import React, { useEffect, useState } from 'react';
import { apiDownload, apiFetch, fireReportAction, isDemoMode } from '../api';
import ReportsTable, { statusBreakdown } from './ReportsTable';
import { CONTENT_TYPE_GROUPS, buildQuery, emptyFilters } from './reports';
import CompositionBar from './charts/CompositionBar';

// The one definition of which report types this page is about, shared with
// the Reports page's "Marketing" content filter so the two can't diverge.
const MARKETING_TYPE_VALUES = CONTENT_TYPE_GROUPS.find(g => g.value === 'marketing').types;

const MARKETING_TYPES = { factsheet: 'Factsheet', marketing: 'Marketing Material' };

const TYPE_PILLS = [
  { value: '', label: 'All' },
  { value: 'factsheet', label: 'Factsheets' },
  { value: 'marketing', label: 'Marketing Material' },
];

const demoMarketing = [
  { id: 3, title: 'Investment Committee Factsheet', client_id: 2, status: 'distributed', team: 'Wealth Management', report_type: 'factsheet', created_at: null },
];

const Marketing = () => {
  const [reports, setReports] = useState([]);
  const [error, setError] = useState('');
  const role = window.localStorage.getItem('lumina_role') || '';
  const canCreate = ['admin', 'editor'].includes(role);

  const [typeFilter, setTypeFilter] = useState('');
  const [filters, setFilters] = useState(emptyFilters);
  const [searchInput, setSearchInput] = useState('');
  const [facets, setFacets] = useState({ teams: [], assetClasses: [] });
  const [clients, setClients] = useState([]);
  const [templates, setTemplates] = useState([]);

  const [form, setForm] = useState({ title: '', client_id: '', team: '', report_type: 'factsheet', template_id: '' });
  const [formMessage, setFormMessage] = useState('');

  const loadReports = () => {
    if (isDemoMode) { setReports(demoMarketing); return; }
    apiFetch(`/api/reports${buildQuery(filters)}`)
      .then(all => setReports(all.filter(r => MARKETING_TYPE_VALUES.includes(r.report_type))))
      .catch(() => setReports(demoMarketing));
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

  useEffect(() => {
    setFilters(current => ({ ...current, report_type: typeFilter }));
  }, [typeFilter]);

  const updateFilter = (key, value) => setFilters(current => ({ ...current, [key]: value }));
  const clearFilters = () => { setFilters(emptyFilters); setSearchInput(''); setTypeFilter(''); };
  const filtersActive = Object.entries(filters).some(([key, value]) => key !== 'report_type' && Boolean(value)) || Boolean(typeFilter);

  const handleAction = async (report, action) => {
    setError('');
    try {
      await fireReportAction(report.id, action);
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
          report_type: form.report_type,
          template_id: form.template_id ? Number(form.template_id) : undefined,
        }),
      });
      setForm({ title: '', client_id: '', team: '', report_type: 'factsheet', template_id: '' });
      loadReports();
    } catch (requestError) { setFormMessage(requestError.message); }
  };

  return (
    <div className="marketing">
      <div className="page-heading">
        <div><span className="eyebrow">Production</span><h1>Fact Sheets &amp; Marketing</h1></div>
        {isDemoMode && <span className="demo-badge">Demo data</span>}
      </div>

      {canCreate && (
        <section className="panel">
          <h2>New fact sheet or marketing piece</h2>
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
                list="marketing-team-suggestions" placeholder="e.g. Institutional Sales"
              />
              <datalist id="marketing-team-suggestions">
                {facets.teams.map(team => <option key={team} value={team} />)}
              </datalist>
            </label>
            <label>Type
              <select value={form.report_type} onChange={e => setForm({ ...form, report_type: e.target.value })}>
                {Object.entries(MARKETING_TYPES).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </label>
            <label>Template (optional — leave blank for a plain PDF)
              <select value={form.template_id} onChange={e => setForm({ ...form, template_id: e.target.value })}>
                <option value="">No template</option>
                {templates.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
            </label>
            <div className="form-actions">
              <button type="submit">Create</button>
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
        <div className="filter-bar">
          <div className="filter-pills">
            {TYPE_PILLS.map(pill => (
              <button
                key={pill.value} type="button"
                className={`filter-pill ${typeFilter === pill.value ? 'active' : ''}`}
                onClick={() => setTypeFilter(pill.value)}
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
          <select className="filter-select" value={filters.status} onChange={e => updateFilter('status', e.target.value)}>
            <option value="">All statuses</option>
            <option value="draft">Draft</option>
            <option value="review">In review</option>
            <option value="compliance">Compliance</option>
            <option value="approved">Approved</option>
            <option value="distributed">Distributed</option>
          </select>
          <input
            className="filter-search" type="search" placeholder="Search title…"
            value={searchInput} onChange={e => setSearchInput(e.target.value)}
          />
          {filtersActive && <button type="button" className="filter-clear" onClick={clearFilters}>Clear filters</button>}
        </div>
        <ReportsTable
          reports={reports} role={role} onAction={handleAction} onExport={handleExport}
          emptyMessage="No fact sheets or marketing materials yet."
        />
      </section>
      {error && <p className="form-message">{error}</p>}
    </div>
  );
};

export default Marketing;
