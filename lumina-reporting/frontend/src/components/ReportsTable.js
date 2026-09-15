import React from 'react';

const STATUS_LABEL = {
  draft: 'Draft',
  review: 'In review',
  compliance: 'Compliance review',
  approved: 'Approved',
  distributed: 'Distributed',
};

const ACTIONS_BY_STATUS = {
  draft: [{ action: 'submit', label: 'Submit for review', roles: ['admin', 'editor'] }],
  review: [
    { action: 'approve', label: 'Approve', roles: ['admin'] },
    { action: 'reject', label: 'Reject', roles: ['admin'] },
  ],
  compliance: [
    { action: 'certify', label: 'Certify', roles: ['compliance'] },
    { action: 'request-changes', label: 'Request changes', roles: ['compliance'] },
  ],
  approved: [{ action: 'distribute', label: 'Distribute', roles: ['admin', 'editor'] }],
  distributed: [],
};

const EXPORT_FORMATS = [
  { value: 'pdf', label: 'PDF' },
  { value: 'pptx', label: 'PowerPoint' },
  { value: 'xlsx', label: 'Excel' },
  { value: 'raw', label: 'Raw data (JSON)' },
];

const ReportsTable = ({ reports, role, onAction, onExport, emptyMessage = 'No reports found.' }) => (
  <table className="reports-table">
    <thead>
      <tr><th>Title</th><th>Client</th><th>Status</th><th>Created</th><th>Actions</th>{onExport && <th>Export</th>}</tr>
    </thead>
    <tbody>
      {reports.map(report => (
        <tr key={report.id}>
          <td>
            {report.title}
            {(report.team || report.report_type) && (
              <div className="reports-table-subtext">
                {[report.team, report.report_type].filter(Boolean).join(' · ')}
              </div>
            )}
          </td>
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
          {onExport && (
            <td>
              <select
                value=""
                onChange={(event) => {
                  const format = event.target.value;
                  if (format) onExport(report, format);
                  event.target.value = '';
                }}
              >
                <option value="">Export as…</option>
                {EXPORT_FORMATS.map(({ value, label }) => (
                  <option key={value} value={value} disabled={!report.template_id && value !== 'pdf'}>
                    {label}
                  </option>
                ))}
              </select>
            </td>
          )}
        </tr>
      ))}
      {reports.length === 0 && (
        <tr><td colSpan={onExport ? 6 : 5} className="reports-table-empty">{emptyMessage}</td></tr>
      )}
    </tbody>
  </table>
);

export default ReportsTable;
