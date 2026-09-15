import React from 'react';
import { Link } from 'react-router-dom';

export const STATUS_LABEL = {
  draft: 'Draft',
  review: 'In review',
  compliance: 'Compliance review',
  approved: 'Approved',
  distributed: 'Distributed',
};

export const ACTIONS_BY_STATUS = {
  draft: [{ action: 'submit', label: 'Submit for review', roles: ['admin', 'editor'], tone: 'neutral' }],
  review: [
    { action: 'approve', label: 'Approve', roles: ['admin'], tone: 'positive' },
    { action: 'reject', label: 'Reject', roles: ['admin'], tone: 'negative' },
  ],
  compliance: [
    { action: 'certify', label: 'Certify', roles: ['compliance'], tone: 'positive' },
    { action: 'request-changes', label: 'Request changes', roles: ['compliance'], tone: 'negative' },
  ],
  approved: [{ action: 'distribute', label: 'Distribute', roles: ['admin', 'editor'], tone: 'neutral' }],
  distributed: [],
};

const STATUS_COLOR = {
  draft: 'var(--c-draft)',
  review: 'var(--c-review)',
  compliance: 'var(--c-compliance)',
  approved: 'var(--c-approved)',
  distributed: 'var(--c-distributed)',
};

// Client-side status tally for a fetched reports list, in canonical pipeline
// order -- feeds CompositionBar without a dedicated backend endpoint.
export const statusBreakdown = (reports) => {
  const counts = reports.reduce((tally, report) => {
    tally[report.status] = (tally[report.status] || 0) + 1;
    return tally;
  }, {});
  return Object.keys(STATUS_LABEL).map(status => ({
    label: STATUS_LABEL[status], value: counts[status] || 0, color: STATUS_COLOR[status],
  }));
};

export const EXPORT_FORMATS = [
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
            <Link to={`/reports/${report.id}`} className="reports-table-title-link">{report.title}</Link>
            {(report.team || report.report_type) && (
              <div className="reports-table-subtext">
                {[report.team, report.report_type].filter(Boolean).join(' · ')}
              </div>
            )}
          </td>
          <td>{report.client_id ? `Client #${report.client_id}` : (report.fund_id ? `Fund #${report.fund_id}` : '—')}</td>
          <td><span className={`status-badge status-${report.status}`}>{STATUS_LABEL[report.status] || report.status}</span></td>
          <td>{report.created_at ? new Date(report.created_at).toLocaleDateString() : '—'}</td>
          <td className="reports-table-actions">
            {(ACTIONS_BY_STATUS[report.status] || [])
              .filter(({ roles }) => roles.includes(role))
              .map(({ action, label, tone }) => (
                <button
                  key={action} type={tone === 'neutral' ? undefined : 'button'}
                  className={tone && tone !== 'neutral' ? `action-btn tone-${tone}` : undefined}
                  onClick={() => onAction(report, action)}
                >
                  {label}
                </button>
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
