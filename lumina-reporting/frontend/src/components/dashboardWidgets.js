import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import BarChart from './charts/BarChart';
import CompositionBar from './charts/CompositionBar';

export const STATUS_ROWS = [
  { key: 'draft', label: 'Draft', color: 'var(--c-draft)' },
  { key: 'review', label: 'In review', color: 'var(--c-review)' },
  { key: 'compliance', label: 'Compliance', color: 'var(--c-compliance)' },
  { key: 'approved', label: 'Approved', color: 'var(--c-approved)' },
  { key: 'distributed', label: 'Distributed', color: 'var(--c-distributed)' },
];

const CATEGORICAL_COLORS = ['var(--cat-1)', 'var(--cat-2)', 'var(--cat-3)', 'var(--cat-4)', 'var(--cat-5)', 'var(--cat-6)'];

const toCategoricalData = (rows) => (rows || []).map((row, index) => ({
  label: row.label,
  value: row.count,
  color: (row.label === 'Other' || row.label === 'Unassigned') ? 'var(--cat-other)' : CATEGORICAL_COLORS[index % CATEGORICAL_COLORS.length],
}));

const toWeeklyData = (rows) => (rows || []).map(row => ({ label: row.label, value: row.count, color: 'var(--brand)' }));

// No label span here -- the widget card's own header already shows the
// title, so a second copy inside the body would just repeat it.
const StatTile = ({ value }) => (
  <article className="metric-card widget-stat-tile"><strong>{value}</strong></article>
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
  const chartData = view === 'status'
    ? STATUS_ROWS.map(row => ({ label: row.label, color: row.color, value: dashboard.reportsByStatus?.[row.key] ?? 0 }))
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
  { to: '/queue', label: 'My Queue', roles: ['admin', 'editor', 'compliance'], countKeys: ['pendingApprovals', 'pendingCompliance'] },
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

const DataSourceHealthWidget = ({ dashboard }) => {
  const failed = dashboard.failedDataSources || [];
  if (failed.length === 0) return <p className="panel-subtitle">All connected data sources are syncing cleanly.</p>;
  return (
    <ul className="report-list">
      {failed.map(source => (
        <li key={source.id}>
          <strong>{source.name}</strong> — {source.message || 'Sync failed'}
        </li>
      ))}
    </ul>
  );
};

// Illustrative -- ReportTransition has real timestamps to compute this
// properly, cut for time this pass; a documented real-data upgrade path.
const DemoSlaTurnaroundWidget = () => (
  <div className="widget-demo-stat">
    <strong>6.4 days</strong>
    <span className="panel-subtitle">Avg. time from Draft to Distributed, last quarter</span>
  </div>
);

// Illustrative -- DistributionLink has no view/open-tracking column at all,
// so this can't be real without a schema change.
const DemoClientEngagementWidget = () => (
  <div className="widget-demo-stat">
    <strong>68%</strong>
    <span className="panel-subtitle">Of shared distribution links have been opened by the client</span>
  </div>
);

// Illustrative -- no due_date/deadline field exists anywhere on Report or Client.
const DemoUpcomingDeadlinesWidget = () => (
  <ul className="report-list">
    <li><strong>Q3 Factsheet refresh</strong> — due in 6 days</li>
    <li><strong>Annual ADV update</strong> — due in 19 days</li>
    <li><strong>Meridian Pension quarterly review</strong> — due in 27 days</li>
  </ul>
);

export const WIDGET_LIBRARY = [
  { id: 'metric-pending-approvals', title: 'Pending approvals', size: 'sm', roles: ['admin', 'editor'], demo: false,
    render: (dashboard) => <StatTile value={dashboard.pendingApprovals ?? 0} /> },
  { id: 'metric-pending-compliance', title: 'Pending compliance', size: 'sm', roles: ['admin', 'compliance'], demo: false,
    render: (dashboard) => <StatTile value={dashboard.pendingCompliance ?? 0} /> },
  { id: 'metric-total-reports', title: 'Total reports', size: 'sm', roles: ['admin', 'editor', 'viewer', 'compliance'], demo: false,
    render: (dashboard) => <StatTile value={dashboard.totalReports ?? 0} /> },
  { id: 'metric-distributed', title: 'Distributed to clients', size: 'sm', roles: ['admin', 'editor', 'viewer'], demo: false,
    render: (dashboard) => <StatTile value={dashboard.reportsByStatus?.distributed ?? 0} /> },
  { id: 'pending-component-reviews', title: 'Components awaiting review', size: 'sm', roles: ['compliance', 'admin'], demo: false,
    render: (dashboard) => <StatTile value={dashboard.pendingComponentReviews ?? 0} /> },
  { id: 'chart-status-pipeline', title: 'Report volume', size: 'lg', roles: ['admin', 'editor', 'viewer', 'compliance'], demo: false,
    render: (dashboard) => <ReportVolumeWidget dashboard={dashboard} /> },
  { id: 'chart-by-team', title: 'Report volume by team', size: 'md', roles: ['admin', 'editor'], demo: false,
    render: (dashboard) => <BarChart title="By team" data={toCategoricalData(dashboard.reportsByTeam)} /> },
  { id: 'chart-by-asset-class', title: 'Report volume by asset class', size: 'md', roles: ['admin', 'viewer'], demo: false,
    render: (dashboard) => <BarChart title="By asset class" data={toCategoricalData(dashboard.reportsByAssetClass)} /> },
  { id: 'chart-by-client', title: 'Report volume by client', size: 'md', roles: ['admin', 'editor'], demo: false,
    render: (dashboard) => <BarChart title="By client" data={toCategoricalData(dashboard.reportsByClient)} /> },
  { id: 'chart-weekly-volume', title: 'Weekly report volume', size: 'md', roles: ['admin', 'editor'], demo: false,
    render: (dashboard) => <BarChart title="Last 8 weeks" data={toWeeklyData(dashboard.reportsByWeek)} unitLabel="reports" /> },
  { id: 'recent-reports', title: 'Recent reports', size: 'md', roles: ['admin', 'editor', 'viewer', 'compliance'], demo: false,
    render: (dashboard) => <RecentReportsWidget dashboard={dashboard} /> },
  { id: 'data-source-health', title: 'Data source health', size: 'sm', roles: ['admin', 'editor'], demo: false,
    render: (dashboard) => <DataSourceHealthWidget dashboard={dashboard} /> },
  { id: 'quick-actions', title: 'Quick actions', size: 'sm', roles: ['admin', 'editor', 'compliance'], demo: false,
    render: (dashboard, role) => <QuickActionsWidget dashboard={dashboard} role={role} /> },
  { id: 'demo-sla-turnaround', title: 'Avg. turnaround time', size: 'md', roles: ['admin', 'compliance'], demo: true,
    render: () => <DemoSlaTurnaroundWidget /> },
  { id: 'demo-client-engagement', title: 'Client portal engagement', size: 'md', roles: ['admin', 'editor'], demo: true,
    render: () => <DemoClientEngagementWidget /> },
  { id: 'demo-upcoming-deadlines', title: 'Upcoming deadlines', size: 'sm', roles: ['compliance'], demo: true,
    render: () => <DemoUpcomingDeadlinesWidget /> },
];

export const WIDGETS_BY_ID = Object.fromEntries(WIDGET_LIBRARY.map(widget => [widget.id, widget]));

export const DEFAULT_LAYOUT = {
  admin: [
    'metric-pending-approvals', 'metric-pending-compliance', 'metric-total-reports', 'metric-distributed',
    'chart-status-pipeline', 'quick-actions', 'chart-by-team', 'recent-reports',
  ],
  editor: [
    'metric-pending-approvals', 'metric-total-reports', 'metric-distributed',
    'chart-status-pipeline', 'quick-actions', 'chart-by-client', 'recent-reports',
  ],
  viewer: [
    'metric-total-reports', 'metric-distributed',
    'chart-status-pipeline', 'chart-by-asset-class', 'recent-reports',
  ],
  compliance: [
    'metric-pending-compliance', 'pending-component-reviews',
    'chart-status-pipeline', 'quick-actions', 'demo-upcoming-deadlines', 'recent-reports',
  ],
};

export const widgetsForRole = (role) => WIDGET_LIBRARY.filter(widget => widget.roles.includes(role));
