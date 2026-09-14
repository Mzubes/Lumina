import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { apiFetch, isDemoMode } from '../api';
import BarChart from './charts/BarChart';

const demoDashboard = {
  pendingApprovals: 3,
  totalReports: 9,
  reportsByStatus: { draft: 2, review: 3, approved: 1, distributed: 3 },
  reportsByTeam: [
    { label: 'Wealth Management', count: 4 }, { label: 'Institutional Sales', count: 3 }, { label: 'Unassigned', count: 2 },
  ],
  reportsByAssetClass: [
    { label: 'Equity', count: 5 }, { label: 'Fixed Income', count: 3 }, { label: 'Unassigned', count: 1 },
  ],
  reportsByClient: [
    { label: 'Acme Institutional', count: 6 }, { label: 'Meridian Capital', count: 3 },
  ],
  failedDataSources: [],
  recentReports: [
    { id: 1, name: 'Q2 Institutional Portfolio Report' },
    { id: 2, name: 'July Performance Summary' },
    { id: 3, name: 'Investment Committee Factsheet' },
  ],
};

const STATUS_ROWS = [
  { key: 'draft', label: 'Draft', color: 'var(--c-draft)' },
  { key: 'review', label: 'In review', color: 'var(--c-review)' },
  { key: 'approved', label: 'Approved', color: 'var(--c-approved)' },
  { key: 'distributed', label: 'Distributed', color: 'var(--c-distributed)' },
];

const CATEGORICAL_COLORS = ['var(--cat-1)', 'var(--cat-2)', 'var(--cat-3)', 'var(--cat-4)', 'var(--cat-5)', 'var(--cat-6)'];

const VIEWS = [
  { key: 'status', label: 'Production Pipeline', subtitle: 'Where every report currently sits in the production pipeline.' },
  { key: 'team', label: 'By Team', subtitle: 'Report volume grouped by team.' },
  { key: 'assetClass', label: 'By Asset Class', subtitle: 'Report volume grouped by the underlying fund’s asset class.' },
  { key: 'client', label: 'By Client', subtitle: 'Report volume grouped by client.' },
];

const toCategoricalData = (rows) => (rows || []).map((row, index) => ({
  label: row.label,
  value: row.count,
  color: (row.label === 'Other' || row.label === 'Unassigned') ? 'var(--cat-other)' : CATEGORICAL_COLORS[index % CATEGORICAL_COLORS.length],
}));

const getViewData = (key, dashboard) => {
  if (key === 'status') {
    return STATUS_ROWS.map(row => ({ label: row.label, color: row.color, value: dashboard.reportsByStatus?.[row.key] ?? 0 }));
  }
  const sourceKey = { team: 'reportsByTeam', assetClass: 'reportsByAssetClass', client: 'reportsByClient' }[key];
  return toCategoricalData(dashboard[sourceKey]);
};

const Dashboard = () => {
  const [data, setData] = useState(null);
  // 'live' | 'demo' | 'unavailable' -- distinct from isDemoMode, so a real
  // fetch failure never gets silently presented as though it were real data.
  const [source, setSource] = useState(isDemoMode ? 'demo' : 'live');
  const [view, setView] = useState('status');

  useEffect(() => {
    if (isDemoMode) { setData(demoDashboard); return; }
    apiFetch('/api/dashboard')
      .then(payload => { setData(payload); setSource('live'); })
      .catch(() => { setData(demoDashboard); setSource('unavailable'); });
  }, []);

  const dashboard = data || demoDashboard;
  const activeView = VIEWS.find(v => v.key === view) || VIEWS[0];
  const chartData = getViewData(view, dashboard);
  const failedSources = dashboard.failedDataSources || [];

  return (
    <div className="dashboard">
      <div className="page-heading">
        <div><span className="eyebrow">Overview</span><h1>Reporting dashboard</h1></div>
        {source === 'demo' && <span className="demo-badge">Demo data</span>}
        {source === 'unavailable' && <span className="demo-badge">Couldn't reach the API — showing sample data</span>}
      </div>

      {failedSources.length > 0 && (
        <div className="alert-banner">
          <span>
            ⚠ <strong>{failedSources.length} data source{failedSources.length === 1 ? '' : 's'}</strong> failed to sync — {failedSources.map(s => s.name).join(', ')}
          </span>
          <Link to="/data-sources">Go to Data Sources →</Link>
        </div>
      )}

      <div className="quick-actions">
        <Link to="/data-sources">Connect a data source</Link>
        <Link to="/templates">New template</Link>
        <Link to="/approvals">
          Review approvals
          {dashboard.pendingApprovals > 0 && <span className="badge-count">{dashboard.pendingApprovals}</span>}
        </Link>
      </div>

      <section className="metric-grid">
        <article className="metric-card"><span>Pending approvals</span><strong>{dashboard.pendingApprovals}</strong></article>
        <article className="metric-card"><span>Total reports</span><strong>{dashboard.totalReports}</strong></article>
        <article className="metric-card"><span>Distributed to clients</span><strong>{dashboard.reportsByStatus?.distributed ?? 0}</strong></article>
      </section>

      <section className="panel">
        <div className="panel-header"><h2>Report volume</h2></div>
        <div className="view-tabs">
          {VIEWS.map(v => (
            <button key={v.key} type="button" className={`view-tab ${view === v.key ? 'active' : ''}`} onClick={() => setView(v.key)}>
              {v.label}
            </button>
          ))}
        </div>
        <p className="panel-subtitle">{activeView.subtitle}</p>
        <BarChart title={activeView.label} data={chartData} />
      </section>

      <section className="panel"><h2>Recent reports</h2><ul className="report-list">
        {dashboard.recentReports.map(report => (
          <li key={report.id}>{report.name}</li>
        ))}
        {dashboard.recentReports.length === 0 && <li>No reports yet.</li>}
      </ul></section>
    </div>
  );
};

export default Dashboard;
