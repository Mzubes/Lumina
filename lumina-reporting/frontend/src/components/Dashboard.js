import React, { useState, useEffect } from 'react';
import { apiFetch, isDemoMode } from '../api';

const demoDashboard = {
  pendingApprovals: 3,
  recentReports: [
    { id: 1, name: 'Q2 Institutional Portfolio Report' },
    { id: 2, name: 'July Performance Summary' },
    { id: 3, name: 'Investment Committee Factsheet' },
  ],
};

const Dashboard = () => {
  const [pendingApprovals, setPendingApprovals] = useState(0);
  const [recentReports, setRecentReports] = useState([]);

  useEffect(() => {
    if (isDemoMode) {
      setPendingApprovals(demoDashboard.pendingApprovals);
      setRecentReports(demoDashboard.recentReports);
      return;
    }
    apiFetch('/api/dashboard')
      .then(data => {
        setPendingApprovals(data.pendingApprovals);
        setRecentReports(data.recentReports);
      }).catch(() => {
        setPendingApprovals(demoDashboard.pendingApprovals);
        setRecentReports(demoDashboard.recentReports);
      });
  }, []);

  return (
    <div className="dashboard">
      <div className="page-heading"><div><span className="eyebrow">Overview</span><h1>Reporting dashboard</h1></div>{isDemoMode && <span className="demo-badge">Demo data</span>}</div>
      <section className="metric-grid">
        <article className="metric-card"><span>Pending approvals</span><strong>{pendingApprovals}</strong></article>
        <article className="metric-card"><span>Reports this month</span><strong>24</strong></article>
        <article className="metric-card"><span>On-time delivery</span><strong>98%</strong></article>
      </section>
      <section className="panel"><h2>Recent reports</h2><ul className="report-list">
        {recentReports.map(report => (
          <li key={report.id}>{report.name}</li>
        ))}
      </ul></section>
    </div>
  );
};

export default Dashboard;
