import React, { useState, useEffect } from 'react';
import { apiFetch, isDemoMode } from '../api';
import BarChart from './charts/BarChart';

const demoDashboard = {
  pendingApprovals: 3,
  totalReports: 9,
  reportsByStatus: { draft: 2, review: 3, approved: 1, distributed: 3 },
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

const Dashboard = () => {
  const [data, setData] = useState(null);
  // 'live' | 'demo' | 'unavailable' -- distinct from isDemoMode, so a real
  // fetch failure never gets silently presented as though it were real data.
  const [source, setSource] = useState(isDemoMode ? 'demo' : 'live');

  useEffect(() => {
    if (isDemoMode) { setData(demoDashboard); return; }
    apiFetch('/api/dashboard')
      .then(payload => { setData(payload); setSource('live'); })
      .catch(() => { setData(demoDashboard); setSource('unavailable'); });
  }, []);

  const dashboard = data || demoDashboard;
  const statusData = STATUS_ROWS.map(row => ({
    label: row.label, color: row.color, value: dashboard.reportsByStatus?.[row.key] ?? 0,
  }));

  return (
    <div className="dashboard">
      <div className="page-heading">
        <div><span className="eyebrow">Overview</span><h1>Reporting dashboard</h1></div>
        {source === 'demo' && <span className="demo-badge">Demo data</span>}
        {source === 'unavailable' && <span className="demo-badge">Couldn't reach the API — showing sample data</span>}
      </div>
      <section className="metric-grid">
        <article className="metric-card"><span>Pending approvals</span><strong>{dashboard.pendingApprovals}</strong></article>
        <article className="metric-card"><span>Total reports</span><strong>{dashboard.totalReports}</strong></article>
        <article className="metric-card"><span>Distributed to clients</span><strong>{dashboard.reportsByStatus?.distributed ?? 0}</strong></article>
      </section>
      <section className="panel">
        <div className="panel-header"><h2>Reports by status</h2></div>
        <p className="panel-subtitle">Where every report currently sits in the production pipeline.</p>
        <BarChart title="Reports by status" data={statusData} />
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
