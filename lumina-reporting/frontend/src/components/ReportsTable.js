import React from 'react';
import { Link } from 'react-router-dom';

// Only ever populated for a legacy (non-diagram) report -- once a report has
// workflow_diagram_id, its status is a denormalized display label computed
// server-side from the diagram's own node names (already human-readable,
// e.g. 'Draft' or a firm-custom 'Portfolio Manager Sign-off'), so this
// lookup would have nothing useful to add. Legacy statuses stay lowercase
// keys, which is why this map exists at all.
export const STATUS_LABEL = {
  draft: 'Draft',
  review: 'In review',
  compliance: 'Compliance review',
  approved: 'Approved',
  distributed: 'Distributed',
};

// Legacy (non-diagram) report action table, keyed by the lowercase status
// key -- action is the exact URL segment (request-changes, not
// request_changes). Diagram-backed reports never consult this: their
// actions come from report.eligibleActions instead (see getReportActions).
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

const CATEGORICAL_COLORS = ['var(--cat-1)', 'var(--cat-2)', 'var(--cat-3)', 'var(--cat-4)', 'var(--cat-5)', 'var(--cat-6)'];

// Deterministic hash-to-categorical-color -- same idiom as
// dashboardWidgets.js's colorForLabel, for a status/step name this table was
// never written to anticipate (a firm-customized workflow step).
const colorForLabel = (label) => {
  let hash = 0;
  for (let i = 0; i < label.length; i += 1) hash = (hash * 31 + label.charCodeAt(i)) >>> 0;
  return CATEGORICAL_COLORS[hash % CATEGORICAL_COLORS.length];
};

// A diagram-backed report's status is already the human-readable label (its
// current step's node name) -- the auto-generated migration diagram even
// reuses the exact legacy words ('Draft', 'Review', ...), just capitalized,
// so matching case-insensitively against the fixed legacy set still finds
// the right color for those; anything else (a firm-custom step name) falls
// back to a computed categorical color.
const colorForStatus = (status) => STATUS_COLOR[status.toLowerCase()] || colorForLabel(status);

// Client-side status tally for a fetched reports list. Legacy statuses keep
// canonical pipeline order and their fixed labels/colors; any other status
// value present in the list (a diagram-backed report's step name) is
// appended after them, in first-seen order, with a computed color.
export const statusBreakdown = (reports) => {
  const counts = reports.reduce((tally, report) => {
    tally[report.status] = (tally[report.status] || 0) + 1;
    return tally;
  }, {});
  // A migrated diagram reproduces the legacy words verbatim, just
  // capitalized ('Distributed' next to a still-legacy report's lowercase
  // 'distributed') -- match case-insensitively and sum both into the one
  // legacy row, or they'd render as two same-labeled rows (a duplicate-key
  // warning, and a wrong split count) instead of one correct total.
  const legacyKeys = new Set(Object.keys(STATUS_LABEL));
  const countForLegacyKey = (key) => Object.entries(counts)
    .reduce((sum, [status, count]) => sum + (status.toLowerCase() === key ? count : 0), 0);
  const legacyRows = Object.keys(STATUS_LABEL).map(status => ({
    label: STATUS_LABEL[status], value: countForLegacyKey(status), color: STATUS_COLOR[status],
  }));
  const extraRows = Object.keys(counts)
    .filter(status => !legacyKeys.has(status.toLowerCase()))
    .map(status => ({ label: status, value: counts[status], color: colorForLabel(status) }));
  return [...legacyRows, ...extraRows];
};

// Best-effort tone for a diagram edge's action_label -- the diagram doesn't
// carry a tone of its own (it's a firm-authored free-text label), so this is
// a heuristic over common verbs, same three tones the legacy fixed table
// used (positive/negative/neutral).
const inferTone = (label) => {
  const lower = label.toLowerCase();
  if (/reject|decline|deny|return|changes/.test(lower)) return 'negative';
  if (/approve|certify|sign.?off|confirm/.test(lower)) return 'positive';
  return 'neutral';
};

// What can this role/user currently do on this report, in the uniform shape
// fireReportAction (api.js) expects. Diagram-backed reports source their
// actions from report.eligibleActions (computed server-side from workflow
// group membership on the report's active step -- no role list to filter by
// here, the backend already scoped it to this caller). Legacy reports keep
// filtering the old fixed ACTIONS_BY_STATUS table by system role.
export const getReportActions = (report, role) => {
  if (report.workflow_diagram_id) {
    return (report.eligibleActions || []).map(({ edge_id, label }) => ({
      key: edge_id, label, tone: inferTone(label), kind: 'edge', edgeId: edge_id,
    }));
  }
  return (ACTIONS_BY_STATUS[report.status] || [])
    .filter(({ roles }) => roles.includes(role))
    .map(({ action, label, tone }) => ({ key: action, label, tone, kind: 'verb', verb: action }));
};

// Flattened action-name -> {label, tone} lookup for the legacy fixed table
// only -- used by reports.js's bulk-action bar, which intersects legacy
// verb names across a selection. Diagram-backed reports use edge_id as their
// action key instead, which isn't a fixed, cross-report-comparable set the
// same way, so bulk actions stay legacy-only (see getReportActions).
export const ACTION_DEFS = Object.values(ACTIONS_BY_STATUS)
  .flat()
  .reduce((lookup, def) => ({ ...lookup, [def.action]: def }), {});

export const EXPORT_FORMATS = [
  { value: 'pdf', label: 'PDF' },
  { value: 'pptx', label: 'PowerPoint' },
  { value: 'xlsx', label: 'Excel' },
  { value: 'raw', label: 'Raw data (JSON)' },
];

// Shared by this table and MyQueue.js, so both render a report's status the
// same way regardless of whether it's one of the 5 fixed legacy words or a
// firm-custom diagram step name.
export const StatusBadge = ({ status }) => (
  STATUS_COLOR[status]
    ? <span className={`status-badge status-${status}`}>{STATUS_LABEL[status] || status}</span>
    : <span className="status-badge status-badge-generic" style={{ '--status-color': colorForStatus(status) }}>{STATUS_LABEL[status] || status}</span>
);

// selectable/selectedIds/onToggleSelect/onToggleSelectAll are all optional --
// only reports.js's bulk-action bar passes them, so marketing.js/pitchbooks.js
// (the table's other two callers) render exactly as before.
const ReportsTable = ({
  reports, role, onAction, onExport, emptyMessage = 'No reports found.',
  selectable = false, selectedIds, onToggleSelect, onToggleSelectAll,
}) => (
  <table className="reports-table">
    <thead>
      <tr>
        {selectable && (
          <th className="reports-table-select-col">
            <input
              type="checkbox"
              checked={reports.length > 0 && reports.every(r => selectedIds.has(r.id))}
              onChange={(event) => onToggleSelectAll(event.target.checked)}
              aria-label="Select all reports"
            />
          </th>
        )}
        <th>Title</th><th>Client</th><th>Status</th><th>Created</th><th>Actions</th>{onExport && <th>Export</th>}
      </tr>
    </thead>
    <tbody>
      {reports.map(report => (
        <tr key={report.id} className={selectable && selectedIds.has(report.id) ? 'is-selected' : undefined}>
          {selectable && (
            <td className="reports-table-select-col">
              <input
                type="checkbox"
                checked={selectedIds.has(report.id)}
                onChange={() => onToggleSelect(report.id)}
                aria-label={`Select ${report.title}`}
              />
            </td>
          )}
          <td>
            <Link to={`/reports/${report.id}`} className="reports-table-title-link">{report.title}</Link>
            {(report.team || report.report_type) && (
              <div className="reports-table-subtext">
                {[report.team, report.report_type].filter(Boolean).join(' · ')}
              </div>
            )}
          </td>
          <td>{report.client_id ? `Client #${report.client_id}` : (report.fund_id ? `Fund #${report.fund_id}` : '—')}</td>
          <td><StatusBadge status={report.status} /></td>
          <td>{report.created_at ? new Date(report.created_at).toLocaleDateString() : '—'}</td>
          <td className="reports-table-actions">
            {getReportActions(report, role).map((reportAction) => (
              <button
                key={reportAction.key} type={reportAction.tone === 'neutral' ? undefined : 'button'}
                className={reportAction.tone && reportAction.tone !== 'neutral' ? `action-btn tone-${reportAction.tone}` : undefined}
                onClick={() => onAction(report, reportAction)}
              >
                {reportAction.label}
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
        <tr><td colSpan={(onExport ? 6 : 5) + (selectable ? 1 : 0)} className="reports-table-empty">{emptyMessage}</td></tr>
      )}
    </tbody>
  </table>
);

export default ReportsTable;
