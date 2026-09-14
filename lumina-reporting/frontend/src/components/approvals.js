import React, { useEffect, useState } from 'react';
import { apiFetch, isDemoMode } from '../api';
import ReportsTable from './ReportsTable';

const demoApprovals = [
  { id: 2, title: 'July Performance Summary', client_id: 1, status: 'review', created_at: null },
];

const Approvals = () => {
  const [reports, setReports] = useState([]);
  const [error, setError] = useState('');
  const role = window.localStorage.getItem('lumina_role') || '';

  const loadApprovals = () => {
    if (isDemoMode) { setReports(demoApprovals); return; }
    apiFetch('/api/reports?status=review').then(setReports).catch(() => setReports(demoApprovals));
  };

  useEffect(loadApprovals, []);

  const handleAction = async (report, action) => {
    setError('');
    try {
      await apiFetch(`/api/reports/${report.id}/${action}`, { method: 'POST' });
      loadApprovals();
    } catch (requestError) { setError(requestError.message); }
  };

  return (
    <div className="approvals">
      <div className="page-heading"><div><span className="eyebrow">Oversight</span><h1>Approvals</h1></div>{isDemoMode && <span className="demo-badge">Demo data</span>}</div>
      <div className="panel">
        <ReportsTable reports={reports} role={role} onAction={handleAction} />
      </div>
      {error && <p className="form-message">{error}</p>}
    </div>
  );
};

export default Approvals;
