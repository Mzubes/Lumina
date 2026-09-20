import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import AreaChart from './charts/AreaChart';
import BarChart from './charts/BarChart';
import CompositionBar from './charts/CompositionBar';
import DonutChart from './charts/DonutChart';
import { IconClipboard, IconDocument, IconSearch, IconShield, IconUsers } from '../icons';

// The 5 legacy statuses keep their fixed named colors; anything else
// (a firm-customized workflow step name) gets a deterministic categorical
// color instead -- same "compute, don't hardcode" idiom as
// ReportsTable.js's statusBreakdown, since a template's workflow diagram
// can introduce step names this list was never written to anticipate.
export const STATUS_ROWS = [
  { key: 'draft', label: 'Draft', color: 'var(--c-draft)' },
  { key: 'review', label: 'In review', color: 'var(--c-review)' },
  { key: 'compliance', label: 'Compliance', color: 'var(--c-compliance)' },
  { key: 'approved', label: 'Approved', color: 'var(--c-approved)' },
  { key: 'distributed', label: 'Distributed', color: 'var(--c-distributed)' },
];
const STATUS_ROW_KEYS = new Set(STATUS_ROWS.map(row => row.key));

const CATEGORICAL_COLORS = ['var(--cat-1)', 'var(--cat-2)', 'var(--cat-3)', 'var(--cat-4)', 'var(--cat-5)', 'var(--cat-6)'];

const colorForLabel = (label) => {
  let hash = 0;
  for (let i = 0; i < label.length; i += 1) hash = (hash * 31 + label.charCodeAt(i)) >>> 0;
  return CATEGORICAL_COLORS[hash % CATEGORICAL_COLORS.length];
};

const toCategoricalData = (rows) => (rows || []).map((row, index) => ({
  label: row.label,
  value: row.count,
  color: (row.label === 'Other' || row.label === 'Unassigned') ? 'var(--cat-other)' : CATEGORICAL_COLORS[index % CATEGORICAL_COLORS.length],
}));

const toWeeklyData = (rows) => (rows || []).map(row => ({ label: row.label, value: row.count, color: 'var(--brand)' }));

// Week-over-week change in report volume, from the same reportsByWeek series
// the "Weekly report volume" chart already plots -- a real comparison against
// the prior period (including the raw previous count, for the "Prev N" line),
// not a fabricated trend number. Needs at least 2 complete weeks; the most
// recent entry can still be a partial week in progress, so it's excluded
// from both sides of the comparison.
const weekOverWeekDelta = (weeks) => {
  const complete = (weeks || []).slice(0, -1);
  if (complete.length < 2) return null;
  const [previous, current] = complete.slice(-2);
  if (!previous.count) return null;
  const pct = Math.round(((current.count - previous.count) / previous.count) * 100);
  return { direction: pct >= 0 ? 'up' : 'down', pct: Math.abs(pct), previous: previous.count };
};

// Header row carries the icon chip (left) and, only where a genuine prior-
// period comparison exists, a tinted delta pill (right) -- most tiles here
// are point-in-time snapshots (pending approvals right now, say) with no
// "previous period" to honestly compare against, so the pill only appears
// when the caller actually passes a delta. The value stays in ink, never
// the accent color, same rule as the icon chip's comment below.
const StatTile = ({ value, icon: Icon, accent, delta }) => (
  <article className="metric-card widget-stat-tile">
    <div className="metric-tile-header">
      {Icon && (
        <span className="metric-icon-chip" style={{ '--chip-color': accent || 'var(--brand)' }}>
          <Icon />
        </span>
      )}
      {delta && (
        <span className={`metric-delta-pill ${delta.direction}`}>
          {delta.direction === 'up' ? '▲' : '▼'} {delta.pct}%
        </span>
      )}
    </div>
    <strong>{value}</strong>
    {delta && <span className="metric-tile-prev">Prev week: {delta.previous.toLocaleString()}</span>}
  </article>
);

const PIPELINE_VIEWS = [
  { key: 'status', label: 'Status', subtitle: 'Where every report currently sits in the production pipeline.', source: null },
  { key: 'team', label: 'By Team', subtitle: 'Report volume grouped by team.', source: 'reportsByTeam' },
  { key: 'assetClass', label: 'By Asset Class', subtitle: 'Report volume grouped by the underlying fund’s asset class.', source: 'reportsByAssetClass' },
  { key: 'client', label: 'By Client', subtitle: 'Report volume grouped by client.', source: 'reportsByClient' },
];

const ReportVolumeWidget = ({ dashboard }) => {
  const [view, setView] = useState('status');
  const activeView = PIPELINE_VIEWS.find(v => v.key === view) || PIPELINE_VIEWS[0];
  const reportsByStatus = dashboard.reportsByStatus || {};
  // A migrated diagram reproduces the legacy words verbatim, just
  // capitalized ('Distributed' next to a still-legacy report's lowercase
  // 'distributed') -- match case-insensitively and sum both into the one
  // legacy row, or they'd render as two same-labeled rows (a duplicate-key
  // warning, and a wrong split count) instead of one correct total.
  const countForLegacyKey = (key) => Object.entries(reportsByStatus)
    .reduce((sum, [status, count]) => sum + (status.toLowerCase() === key ? count : 0), 0);
  const extraStatusRows = Object.keys(reportsByStatus)
    .filter(key => !STATUS_ROW_KEYS.has(key.toLowerCase()) && reportsByStatus[key] > 0)
    .map(key => ({ label: key, color: colorForLabel(key), value: reportsByStatus[key] }));
  const chartData = view === 'status'
    ? [
        ...STATUS_ROWS.map(row => ({ label: row.label, color: row.color, value: countForLegacyKey(row.key) })),
        ...extraStatusRows,
      ]
    : toCategoricalData(dashboard[activeView.source]);

  return (
    <>
      <div className="view-tabs">
        {PIPELINE_VIEWS.map(v => (
          <button key={v.key} type="button" className={`view-tab ${view === v.key ? 'active' : ''}`} onClick={() => setView(v.key)}>
            {v.label}
          </button>
        ))}
      </div>
      <p className="panel-subtitle">{activeView.subtitle}</p>
      <BarChart title={activeView.label} data={chartData} />
      {view === 'status' && (
        <div className="dashboard-composition">
          <h3 className="composition-heading">Pipeline mix</h3>
          <CompositionBar title="Pipeline mix" data={chartData} />
        </div>
      )}
    </>
  );
};

const QUICK_ACTIONS = [
  { to: '/data-sources', label: 'Connect a data source', roles: ['admin', 'editor'] },
  { to: '/templates', label: 'New template', roles: ['admin', 'editor'] },
  // Approvals + Compliance were two separate quick actions; My Queue merges
  // them into one destination, badge count summed across both -- component
  // review counts are role-specific and not worth the added complexity here.
  { to: '/queue', label: 'My Queue', roles: ['admin', 'editor'], countKeys: ['pendingApprovals', 'pendingCompliance'] },
];

const QuickActionsWidget = ({ dashboard, role }) => {
  const actions = QUICK_ACTIONS.filter(action => action.roles.includes(role));
  return (
    <div className="quick-actions">
      {actions.map((action) => {
        const count = (action.countKeys || []).reduce((sum, key) => sum + (dashboard[key] || 0), 0);
        return (
          <Link key={action.to} to={action.to}>
            {action.label}
            {count > 0 && <span className="badge-count">{count}</span>}
          </Link>
        );
      })}
      {actions.length === 0 && <p className="panel-subtitle">No quick actions for this role.</p>}
    </div>
  );
};

const RecentReportsWidget = ({ dashboard }) => (
  <ul className="report-list">
    {(dashboard.recentReports || []).map(report => <li key={report.id}>{report.name}</li>)}
    {(dashboard.recentReports || []).length === 0 && <li>No reports yet.</li>}
  </ul>
);

// Still illustrative -- DistributionLink has no view/open-tracking column at
// all, so this one can't be real without a schema change. The turnaround and
// deadline widgets that used to sit beside it are now real: Report.due_date
// exists, and the Management tab computes turnaround from ReportTransition.
const DemoClientEngagementWidget = () => (
  <div className="widget-demo-stat">
    <strong>68%</strong>
    <span className="panel-subtitle">Of shared distribution links have been opened by the client</span>
  </div>
);

const UpcomingDeadlinesWidget = ({ dashboard }) => {
  const deadlines = dashboard.upcomingDeadlines || [];
  if (deadlines.length === 0) return <p className="panel-subtitle">No open report has a due date set.</p>;
  return (
    <ul className="report-list">
      {deadlines.map(row => (
        <li key={row.reportId}>
          <Link to={`/reports/${row.reportId}`}>{row.title}</Link>{' '}
          <span className={row.daysRemaining < 0 ? 'deadline-overdue' : 'panel-subtitle'}>
            {/* Past due reads as past due, not as "in -3 days". */}
            {row.daysRemaining < 0
              ? `${Math.abs(row.daysRemaining)} ${Math.abs(row.daysRemaining) === 1 ? 'day' : 'days'} overdue`
              : row.daysRemaining === 0 ? 'due today'
              : `due in ${row.daysRemaining} ${row.daysRemaining === 1 ? 'day' : 'days'}`}
          </span>
        </li>
      ))}
    </ul>
  );
};

// ---------- Production Hub: real-data widgets ----------

const SLA_TONES = {
  sla_breached: { label: 'Breached', color: 'var(--c-critical)' },
  flagged: { label: 'Flagged', color: 'var(--c-review)' },
  watch: { label: 'Watch', color: 'var(--c-compliance)' },
  on_track: { label: 'On track', color: 'var(--c-approved)' },
};

const DataSourceHealthListWidget = ({ dashboard }) => {
  const sources = dashboard.dataSources || [];
  if (sources.length === 0) return <p className="panel-subtitle">No data sources connected yet.</p>;
  return (
    <ul className="health-list">
      {sources.map(source => (
        <li key={source.id}>
          <span className={`health-dot health-${source.status}`} aria-hidden="true" />
          <span className="health-name">{source.name}</span>
          <span className="health-detail">
            {/* A source that has never run is its own state, not a healthy
                one -- saying "never synced" is the whole point of listing it. */}
            {source.status === 'error' ? (source.message || 'Sync failed')
              : source.status === 'never' ? 'Never synced'
              : source.lastSyncedAt ? `Synced ${new Date(source.lastSyncedAt).toLocaleDateString()}` : 'Synced'}
          </span>
        </li>
      ))}
    </ul>
  );
};

const WorkflowStageProgressWidget = ({ dashboard }) => {
  const stages = dashboard.workflowStageProgress || [];
  if (stages.length === 0) return <p className="panel-subtitle">Nothing is currently in flight.</p>;
  return (
    <>
      <p className="panel-subtitle">
        Reports sitting on each workflow step right now. A report on a parallel branch counts on every step it occupies.
      </p>
      <BarChart title="By stage" data={toCategoricalData(stages)} />
    </>
  );
};

const MissingContentWidget = ({ dashboard }) => {
  const gaps = dashboard.missingContent || [];
  if (gaps.length === 0) return <p className="panel-subtitle">Every in-flight report has its reviewable content signed off.</p>;
  return (
    <ul className="report-list">
      {gaps.slice(0, 8).map(gap => (
        <li key={`${gap.reportId}-${gap.componentId}`}>
          <Link to={`/reports/${gap.reportId}`}>{gap.reportTitle}</Link> — {gap.componentLabel}
        </li>
      ))}
      {gaps.length > 8 && <li className="panel-subtitle">+{gaps.length - 8} more</li>}
    </ul>
  );
};

const DeliverySlaWidget = ({ dashboard }) => {
  const counts = dashboard.deliverySla || {};
  const data = Object.entries(SLA_TONES)
    .map(([key, tone]) => ({ label: tone.label, value: counts[key] || 0, color: tone.color }));
  if (data.every(row => row.value === 0)) return <p className="panel-subtitle">No clients to score yet.</p>;
  return (
    <>
      <p className="panel-subtitle">Every client's computed delivery status — the same one the Internal Portal badges.</p>
      <CompositionBar title="Delivery SLA" data={data} unitLabel="clients" />
    </>
  );
};

const SlaAtRiskWidget = ({ dashboard }) => {
  const atRisk = dashboard.slaAtRisk || {};
  const breached = atRisk.breached ?? 0;
  return (
    <>
      <StatTile value={breached} icon={IconShield} accent={breached > 0 ? 'var(--c-critical)' : 'var(--c-approved)'} />
      <span className="panel-subtitle">
        {atRisk.approaching ?? 0} more due within {atRisk.windowDays ?? 3} days
      </span>
    </>
  );
};

// ---------- Management tab ----------

// Management data arrives from its own endpoint, so every widget here has to
// render something sane before it lands rather than assuming a shape.
const SlowestStepsWidget = ({ management }) => {
  const steps = management?.slowestSteps;
  if (!management) return <p className="panel-subtitle">Loading…</p>;
  if (!steps || steps.length === 0) {
    return (
      <p className="panel-subtitle">
        Not enough completed steps yet — a step needs at least {management.minVisitsForAverage ?? 2} finished
        visits before an average means anything.
      </p>
    );
  }
  return (
    <>
      <p className="panel-subtitle">Average <strong>hours</strong> per completed visit. Wall-clock, so it includes nights and weekends.</p>
      <BarChart
        title="Slowest steps" unitLabel="hours"
        data={steps.map((step, index) => ({
          label: step.label, value: step.avgHours, valueLabel: `${step.avgHours}h`,
          color: CATEGORICAL_COLORS[index % CATEGORICAL_COLORS.length],
        }))}
      />
    </>
  );
};

const BottleneckByGroupWidget = ({ management }) => {
  if (!management) return <p className="panel-subtitle">Loading…</p>;
  const rows = management.bottleneckByGroup || [];
  if (rows.length === 0) return <p className="panel-subtitle">No work is queued on any group right now.</p>;
  return (
    <table className="scorecard-table">
      <thead><tr><th>Group</th><th>Waiting</th><th>Oldest</th></tr></thead>
      <tbody>
        {rows.map(row => (
          <tr key={row.label}>
            <td>{row.label}</td>
            <td>{row.count}</td>
            <td>{row.oldestDays} {row.oldestDays === 1 ? 'day' : 'days'}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
};

const TeamScorecardWidget = ({ management }) => {
  if (!management) return <p className="panel-subtitle">Loading…</p>;
  const rows = management.teamScorecard || [];
  if (rows.length === 0) return <p className="panel-subtitle">No reports to score yet.</p>;
  return (
    <table className="scorecard-table">
      <thead><tr><th>Team</th><th>Open</th><th>Delivered</th><th>Avg. turnaround</th></tr></thead>
      <tbody>
        {rows.map(row => (
          <tr key={row.label}>
            <td>{row.label}</td>
            <td>{row.open}</td>
            <td>{row.delivered}</td>
            {/* An em dash, not a zero: a team that hasn't delivered yet has
                no turnaround, which is not the same as a fast one. */}
            <td>{row.avgTurnaroundDays == null ? '—' : `${row.avgTurnaroundDays} days`}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
};

// Every widget declares which tab it belongs to. Day-to-day answers "what
// do I work on now"; Management answers "how is production performing" --
// the same split the design draws, and the reason the Management widgets
// read from their own payload (see MANAGEMENT_WIDGET_IDS below).
export const TABS = [
  { key: 'dayToDay', label: 'Day-to-day' },
  { key: 'management', label: 'Management' },
];

export const WIDGET_LIBRARY = [
  { id: 'metric-pending-approvals', title: 'Pending approvals', tab: 'dayToDay', size: 'sm', roles: ['admin', 'editor'], demo: false,
    render: (dashboard) => <StatTile value={dashboard.pendingApprovals ?? 0} icon={IconClipboard} accent="var(--c-review)" /> },
  { id: 'metric-pending-compliance', title: 'Pending compliance', tab: 'dayToDay', size: 'sm', roles: ['admin', 'editor'], demo: false,
    render: (dashboard) => <StatTile value={dashboard.pendingCompliance ?? 0} icon={IconShield} accent="var(--c-compliance)" /> },
  { id: 'metric-total-reports', title: 'Total reports', tab: 'dayToDay', size: 'sm', roles: ['admin', 'editor', 'viewer'], demo: false,
    render: (dashboard) => (
      <StatTile value={dashboard.totalReports ?? 0} icon={IconDocument} accent="var(--cat-1)" delta={weekOverWeekDelta(dashboard.reportsByWeek)} />
    ) },
  { id: 'metric-distributed', title: 'Distributed to clients', tab: 'dayToDay', size: 'sm', roles: ['admin', 'editor', 'viewer'], demo: false,
    render: (dashboard) => <StatTile value={dashboard.reportsByStatus?.distributed ?? 0} icon={IconUsers} accent="var(--c-approved)" /> },
  { id: 'metric-sla-at-risk', title: 'SLA at risk', tab: 'dayToDay', size: 'sm', roles: ['admin', 'editor'], demo: false,
    render: (dashboard) => <SlaAtRiskWidget dashboard={dashboard} /> },
  { id: 'pending-component-reviews', title: 'Components awaiting review', tab: 'dayToDay', size: 'sm', roles: ['admin', 'editor'], demo: false,
    render: (dashboard) => <StatTile value={dashboard.pendingComponentReviews ?? 0} icon={IconSearch} accent="var(--cat-5)" /> },
  { id: 'chart-status-pipeline', title: 'Report volume', tab: 'dayToDay', size: 'lg', roles: ['admin', 'editor', 'viewer'], demo: false,
    render: (dashboard) => <ReportVolumeWidget dashboard={dashboard} /> },
  { id: 'chart-workflow-stages', title: 'Where work is sitting', tab: 'dayToDay', size: 'md', roles: ['admin', 'editor'], demo: false,
    render: (dashboard) => <WorkflowStageProgressWidget dashboard={dashboard} /> },
  { id: 'delivery-sla', title: 'Delivery SLA', tab: 'dayToDay', size: 'md', roles: ['admin', 'editor'], demo: false,
    render: (dashboard) => <DeliverySlaWidget dashboard={dashboard} /> },
  { id: 'chart-by-team', title: 'Report volume by team', tab: 'dayToDay', size: 'md', roles: ['admin', 'editor'], demo: false,
    render: (dashboard) => <BarChart title="By team" data={toCategoricalData(dashboard.reportsByTeam)} /> },
  { id: 'chart-by-asset-class', title: 'Report volume by asset class', tab: 'dayToDay', size: 'md', roles: ['admin', 'viewer'], demo: false,
    render: (dashboard) => <DonutChart title="By asset class" centerLabel="Reports" data={toCategoricalData(dashboard.reportsByAssetClass)} /> },
  { id: 'chart-by-client', title: 'Report volume by client', tab: 'dayToDay', size: 'md', roles: ['admin', 'editor'], demo: false,
    render: (dashboard) => <BarChart title="By client" data={toCategoricalData(dashboard.reportsByClient)} /> },
  { id: 'chart-weekly-volume', title: 'Weekly report volume', tab: 'dayToDay', size: 'md', roles: ['admin', 'editor'], demo: false,
    render: (dashboard) => <AreaChart title="Last 8 weeks" data={toWeeklyData(dashboard.reportsByWeek)} /> },
  { id: 'recent-reports', title: 'Recent reports', tab: 'dayToDay', size: 'md', roles: ['admin', 'editor', 'viewer'], demo: false,
    render: (dashboard) => <RecentReportsWidget dashboard={dashboard} /> },
  { id: 'upcoming-deadlines', title: 'Upcoming deadlines', tab: 'dayToDay', size: 'md', roles: ['admin', 'editor'], demo: false,
    render: (dashboard) => <UpcomingDeadlinesWidget dashboard={dashboard} /> },
  { id: 'missing-content', title: 'Missing content', tab: 'dayToDay', size: 'md', roles: ['admin', 'editor'], demo: false,
    render: (dashboard) => <MissingContentWidget dashboard={dashboard} /> },
  // 'sm' is the stat-tile width (a quarter row). These two are list/button
  // panels whose content needs a half row to breathe -- at 'sm' they left a
  // dead gutter beside every chart they sat next to.
  { id: 'data-source-health', title: 'Data source health', tab: 'dayToDay', size: 'md', roles: ['admin', 'editor'], demo: false,
    render: (dashboard) => <DataSourceHealthListWidget dashboard={dashboard} /> },
  { id: 'quick-actions', title: 'Quick actions', tab: 'dayToDay', size: 'md', roles: ['admin', 'editor'], demo: false,
    render: (dashboard, role) => <QuickActionsWidget dashboard={dashboard} role={role} /> },
  { id: 'demo-client-engagement', title: 'Client portal engagement', tab: 'dayToDay', size: 'md', roles: ['admin', 'editor'], demo: true,
    render: () => <DemoClientEngagementWidget /> },

  // Management tab. These read `management`, the second payload.
  { id: 'mgmt-team-scorecard', title: 'Team scorecard', tab: 'management', size: 'lg', roles: ['admin', 'editor', 'viewer'], demo: false,
    render: (dashboard, role, management) => <TeamScorecardWidget management={management} /> },
  { id: 'mgmt-slowest-steps', title: 'Slowest steps', tab: 'management', size: 'md', roles: ['admin', 'editor', 'viewer'], demo: false,
    render: (dashboard, role, management) => <SlowestStepsWidget management={management} /> },
  { id: 'mgmt-bottleneck-by-group', title: 'Bottlenecks by group', tab: 'management', size: 'md', roles: ['admin', 'editor', 'viewer'], demo: false,
    render: (dashboard, role, management) => <BottleneckByGroupWidget management={management} /> },
  { id: 'mgmt-production-by-team', title: 'Production by team', tab: 'management', size: 'md', roles: ['admin', 'editor', 'viewer'], demo: false,
    render: (dashboard) => <BarChart title="By team" data={toCategoricalData(dashboard.reportsByTeam)} /> },
  { id: 'mgmt-weekly-volume', title: 'Weekly report volume', tab: 'management', size: 'md', roles: ['admin', 'editor', 'viewer'], demo: false,
    render: (dashboard) => <AreaChart title="Last 8 weeks" data={toWeeklyData(dashboard.reportsByWeek)} /> },
];

export const WIDGETS_BY_ID = Object.fromEntries(WIDGET_LIBRARY.map(widget => [widget.id, widget]));

// Which widgets need the Management payload. The Production Hub uses this to
// decide whether to fetch it at all, so a user who never opens that tab
// never pays for its queries.
export const MANAGEMENT_WIDGET_IDS = new Set(
  WIDGET_LIBRARY.filter(widget => widget.tab === 'management').map(widget => widget.id),
);

// Ordered so each row tiles completely against the 12-column grid: four
// quarter-width stat tiles, then a full-width chart, then half-width pairs.
// A layout that leaves a half row empty reads as a broken grid, not as
// breathing room.
export const DEFAULT_LAYOUT = {
  dayToDay: {
    admin: [
      'metric-pending-approvals', 'metric-pending-compliance', 'metric-sla-at-risk', 'metric-distributed',
      'chart-status-pipeline',
      'quick-actions', 'chart-workflow-stages',
      'upcoming-deadlines', 'data-source-health',
      'delivery-sla', 'missing-content',
    ],
    editor: [
      'metric-pending-approvals', 'metric-total-reports', 'metric-sla-at-risk', 'pending-component-reviews',
      'chart-status-pipeline',
      'quick-actions', 'chart-workflow-stages',
      'upcoming-deadlines', 'missing-content',
      'recent-reports', 'data-source-health',
    ],
    // A viewer can only see five widgets, which is 2.5 rows' worth -- one row
    // is unavoidably partial. Ordered so the two stat tiles share a full row
    // with a half-width chart and the partial row falls last, where a gap is
    // least conspicuous, rather than first.
    viewer: [
      'metric-total-reports', 'metric-distributed', 'chart-by-asset-class',
      'chart-status-pipeline', 'recent-reports',
    ],
  },
  management: {
    admin: ['mgmt-team-scorecard', 'mgmt-slowest-steps', 'mgmt-bottleneck-by-group', 'mgmt-production-by-team', 'mgmt-weekly-volume'],
    editor: ['mgmt-team-scorecard', 'mgmt-slowest-steps', 'mgmt-bottleneck-by-group', 'mgmt-production-by-team', 'mgmt-weekly-volume'],
    viewer: ['mgmt-team-scorecard', 'mgmt-production-by-team', 'mgmt-weekly-volume'],
  },
};

export const widgetsForRole = (role, tab = 'dayToDay') =>
  WIDGET_LIBRARY.filter(widget => widget.tab === tab && widget.roles.includes(role));

export const defaultLayout = (role, tab = 'dayToDay') => {
  const byRole = DEFAULT_LAYOUT[tab] || DEFAULT_LAYOUT.dayToDay;
  return byRole[role] || byRole.viewer || [];
};
