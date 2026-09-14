import React, { useEffect, useState } from 'react';
import { apiDownload, apiFetch, isDemoMode } from '../api';
import ReportsTable from './ReportsTable';

const demoReports = [
  { id: 1, title: 'Q2 Institutional Portfolio Report', client_id: 1, status: 'draft', created_at: null },
  { id: 2, title: 'July Performance Summary', client_id: 1, status: 'review', created_at: null },
  { id: 3, title: 'Investment Committee Factsheet', client_id: 2, status: 'distributed', created_at: null },
];

const Reports = () => {
  const [reports, setReports] = useState([]);
  const [error, setError] = useState('');
  const role = window.localStorage.getItem('lumina_role') || '';

  const loadReports = () => {
    if (isDemoMode) { setReports(demoReports); return; }
    apiFetch('/api/reports').then(setReports).catch(() => setReports(demoReports));
  };

  useEffect(loadReports, []);

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

  return (
    <div className="reports">
      <div className="page-heading"><div><span className="eyebrow">Production</span><h1>Reports</h1></div>{isDemoMode && <span className="demo-badge">Demo data</span>}</div>
      <div className="panel">
        <ReportsTable reports={reports} role={role} onAction={handleAction} onExport={handleExport} />
      </div>
      {error && <p className="form-message">{error}</p>}
    </div>
  );
};

export default Reports;
