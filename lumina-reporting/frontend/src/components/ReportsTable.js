import React from 'react';

const STATUS_LABEL = {
  draft: 'Draft',
  review: 'In review',
  approved: 'Approved',
  distributed: 'Distributed',
};

const ACTIONS_BY_STATUS = {
  draft: [{ action: 'submit', label: 'Submit for review', roles: ['admin', 'editor'] }],
  review: [
    { action: 'approve', label: 'Approve', roles: ['admin'] },
    { action: 'reject', label: 'Reject', roles: ['admin'] },
  ],
  approved: [{ action: 'distribute', label: 'Distribute', roles: ['admin', 'editor'] }],
  distributed: [],
};

const ReportsTable = ({ reports, role, onAction }) => (
  <table className="reports-table">
    <thead>
      <tr><th>Title</th><th>Client</th><th>Status</th><th>Created</th><th>Actions</th></tr>
    </thead>
    <tbody>
      {reports.map(report => (
        <tr key={report.id}>
          <td>{report.title}</td>
          <td>Client #{report.client_id}</td>
          <td><span className={`status-badge status-${report.status}`}>{STATUS_LABEL[report.status] || report.status}</span></td>
          <td>{report.created_at ? new Date(report.created_at).toLocaleDateString() : '—'}</td>
          <td className="reports-table-actions">
            {(ACTIONS_BY_STATUS[report.status] || [])
              .filter(({ roles }) => roles.includes(role))
              .map(({ action, label }) => (
                <button key={action} onClick={() => onAction(report, action)}>{label}</button>
              ))}
          </td>
        </tr>
      ))}
      {reports.length === 0 && (
        <tr><td colSpan={5} className="reports-table-empty">No reports found.</td></tr>
      )}
    </tbody>
  </table>
);

export default ReportsTable;
