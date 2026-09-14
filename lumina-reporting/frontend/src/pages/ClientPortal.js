import React, { useEffect, useState } from 'react';
import { apiBaseUrl, apiFetch, isDemoMode } from '../api';

const demoReports = [
  { id: 1, title: 'Q2 Institutional Portfolio Report', file_path: null, created_at: null },
  { id: 2, title: 'July Performance Summary', file_path: null, created_at: null },
];

const ClientPortal = () => {
  const [reports, setReports] = useState([]);

  useEffect(() => {
    if (isDemoMode) { setReports(demoReports); return; }
    apiFetch('/api/reports').then(setReports).catch(() => setReports(demoReports));
  }, []);

  return (
    <div className="client-portal">
      <div className="page-heading"><div><span className="eyebrow">Client experience</span><h1>Client Portal</h1></div>{isDemoMode && <span className="demo-badge">Demo data</span>}</div>
      <div className="panel"><h2>Your reports</h2><ul className="report-list">
        {reports.map(report => (
          <li key={report.id}>
            {report.title}
            {report.file_path
              ? <a href={`${apiBaseUrl}${report.file_path}`} target="_blank" rel="noreferrer"><button>View</button></a>
              : <button disabled>View</button>}
          </li>
        ))}
        {reports.length === 0 && <li>No reports have been distributed to you yet.</li>}
      </ul></div>
    </div>
  );
};

export default ClientPortal;
