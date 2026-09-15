import React, { useEffect, useState } from 'react';
import { apiFetch, isDemoMode } from '../api';
import ReportsTable from './ReportsTable';

const demoCompliance = [
  { id: 4, title: 'Q3 Sales Pitch Book', client_id: 1, status: 'compliance', created_at: null },
];

const Compliance = () => {
  const [reports, setReports] = useState([]);
  const [error, setError] = useState('');
  const role = window.localStorage.getItem('lumina_role') || '';

  const loadQueue = () => {
    if (isDemoMode) { setReports(demoCompliance); return; }
    apiFetch('/api/reports?status=compliance').then(setReports).catch(() => setReports(demoCompliance));
  };

  useEffect(loadQueue, []);

  const handleAction = async (report, action) => {
    setError('');
    try {
      await apiFetch(`/api/reports/${report.id}/${action}`, { method: 'POST' });
      loadQueue();
    } catch (requestError) { setError(requestError.message); }
  };

  return (
    <div className="compliance">
      <div className="page-heading"><div><span className="eyebrow">Oversight</span><h1>Compliance</h1></div>{isDemoMode && <span className="demo-badge">Demo data</span>}</div>
      <div className="panel">
        <div className="panel-header"><h2>Awaiting compliance review</h2></div>
        <p className="panel-subtitle">
          {reports.length === 0
            ? 'Nothing waiting on compliance review right now.'
            : `${reports.length} report${reports.length === 1 ? '' : 's'} need${reports.length === 1 ? 's' : ''} certification.`}
        </p>
        <ReportsTable
          reports={reports} role={role} onAction={handleAction}
          emptyMessage="Nothing waiting on compliance review right now."
        />
      </div>
      {error && <p className="form-message">{error}</p>}
    </div>
  );
};

export default Compliance;
