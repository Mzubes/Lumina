import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { DndContext, KeyboardSensor, PointerSensor, closestCenter, useSensor, useSensors } from '@dnd-kit/core';
import { SortableContext, arrayMove, rectSortingStrategy, sortableKeyboardCoordinates, useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { apiFetch, isDemoMode } from '../api';
import { MANAGEMENT_WIDGET_IDS, TABS, WIDGETS_BY_ID, defaultLayout, widgetsForRole } from './dashboardWidgets';
import PageGreeting from './PageGreeting';

const demoDashboard = {
  pendingApprovals: 3,
  pendingCompliance: 1,
  totalReports: 9,
  reportsByStatus: { draft: 2, review: 3, compliance: 1, approved: 1, distributed: 3 },
  reportsByTeam: [
    { label: 'Wealth Management', count: 4 }, { label: 'Institutional Sales', count: 3 }, { label: 'Unassigned', count: 2 },
  ],
  reportsByAssetClass: [
    { label: 'Equity', count: 5 }, { label: 'Fixed Income', count: 3 }, { label: 'Unassigned', count: 1 },
  ],
  reportsByClient: [
    { label: 'Acme Institutional', count: 6 }, { label: 'Meridian Capital', count: 3 },
  ],
  failedDataSources: [],
  recentReports: [
    { id: 1, name: 'Q2 Institutional Portfolio Report' },
    { id: 2, name: 'July Performance Summary' },
    { id: 3, name: 'Investment Committee Factsheet' },
  ],
  reportsByWeek: [
    { label: 'W28', count: 1 }, { label: 'W29', count: 2 }, { label: 'W30', count: 1 }, { label: 'W31', count: 3 },
    { label: 'W32', count: 2 }, { label: 'W33', count: 1 }, { label: 'W34', count: 4 }, { label: 'W35', count: 2 },
  ],
  pendingComponentReviews: 2,
  dataSources: [
    { id: 1, name: 'Snowflake — Positions', type: 'snowflake', status: 'success', message: null, lastSyncedAt: null },
    { id: 2, name: 'Custodian API', type: 'api', status: 'never', message: null, lastSyncedAt: null },
  ],
  missingContent: [
    { reportId: 2, reportTitle: 'July Performance Summary', componentId: 'c1', componentLabel: 'Commentary' },
    { reportId: 2, reportTitle: 'July Performance Summary', componentId: 'c2', componentLabel: 'Holdings' },
  ],
  workflowStageProgress: [{ label: 'Compliance review', count: 3 }, { label: 'Drafting', count: 2 }],
  slaAtRisk: { breached: 1, approaching: 2, windowDays: 3 },
  deliverySla: { sla_breached: 1, flagged: 1, watch: 2, on_track: 5 },
  upcomingDeadlines: [
    { reportId: 2, title: 'July Performance Summary', dueDate: null, daysRemaining: -2 },
    { reportId: 1, title: 'Q2 Institutional Portfolio Report', dueDate: null, daysRemaining: 6 },
  ],
};

const demoManagement = {
  slowestSteps: [
    { label: 'Compliance review', avgHours: 38.4, visits: 6 },
    { label: 'Portfolio sign-off', avgHours: 12.1, visits: 9 },
    { label: 'Drafting', avgHours: 6.5, visits: 11 },
  ],
  bottleneckByGroup: [
    { label: 'Compliance', count: 3, oldestDays: 5.2 },
    { label: 'Client Reporting', count: 1, oldestDays: 0.4 },
  ],
  teamScorecard: [
    { label: 'Wealth Management', total: 5, open: 2, delivered: 3, avgTurnaroundDays: 6.4 },
    { label: 'Institutional Sales', total: 4, open: 4, delivered: 0, avgTurnaroundDays: null },
  ],
  minVisitsForAverage: 2,
};

// Each tab keeps its own arrangement -- they hold different widgets, so one
// shared list would mean rearranging Management silently rewrote Day-to-day.
// The Day-to-day key is the original unsuffixed one, so an existing saved
// layout carries over instead of being reset by this change.
const layoutKey = (role, tab) =>
  `lumina_dashboard_layout_${role || 'viewer'}${tab === 'dayToDay' ? '' : `_${tab}`}`;

const loadLayout = (role, tab) => {
  try {
    const raw = window.localStorage.getItem(layoutKey(role, tab));
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed.visible)) return parsed.visible;
    }
  } catch { /* corrupt/blocked storage -- fall through to defaults */ }
  return defaultLayout(role, tab);
};

const saveLayout = (role, tab, visible) => {
  try { window.localStorage.setItem(layoutKey(role, tab), JSON.stringify({ visible })); } catch { /* per-viewer convenience only */ }
};

const TAB_KEY = 'lumina_production_hub_tab';

const SortableWidget = ({ id, size, title, demo, onHide, children }) => {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id });
  const style = { transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.4 : 1 };

  return (
    <section ref={setNodeRef} style={style} className={`panel widget-card widget-size-${size} ${isDragging ? 'is-dragging' : ''}`}>
      <div className="panel-header widget-card-header">
        <button type="button" className="widget-drag-handle" aria-label={`Reorder ${title}`} {...attributes} {...listeners}>⠿</button>
        <h2>{title}</h2>
        {demo && <span className="demo-badge">Demo data</span>}
        <button type="button" className="widget-hide-btn" aria-label={`Hide ${title}`} onClick={onHide}>×</button>
      </div>
      {children}
    </section>
  );
};

const Dashboard = () => {
  const role = window.localStorage.getItem('lumina_role') || 'viewer';

  const [data, setData] = useState(null);
  // The Management tab's aggregates come from their own endpoint and are
  // fetched lazily -- see the effect below.
  const [management, setManagement] = useState(null);
  // 'live' | 'demo' | 'unavailable' -- distinct from isDemoMode, so a real
  // fetch failure never gets silently presented as though it were real data.
  const [source, setSource] = useState(isDemoMode ? 'demo' : 'live');
  const [tab, setTab] = useState(() => {
    const saved = window.localStorage.getItem(TAB_KEY);
    return TABS.some(t => t.key === saved) ? saved : 'dayToDay';
  });
  const [visibleIds, setVisibleIds] = useState(() => loadLayout(role, tab));

  useEffect(() => {
    if (isDemoMode) { setData(demoDashboard); return; }
    apiFetch('/api/dashboard')
      .then(payload => { setData(payload); setSource('live'); })
      .catch(() => { setData(demoDashboard); setSource('unavailable'); });
  }, []);

  const availableWidgets = widgetsForRole(role, tab);
  const availableIds = new Set(availableWidgets.map(w => w.id));
  const widgetIds = visibleIds.filter(id => availableIds.has(id) && WIDGETS_BY_ID[id]);

  // Fetched the first time a management widget is actually on screen, and
  // only once -- a user who never opens that tab never runs its queries.
  const needsManagement = widgetIds.some(id => MANAGEMENT_WIDGET_IDS.has(id));
  useEffect(() => {
    if (!needsManagement || management) return;
    if (isDemoMode) { setManagement(demoManagement); return; }
    apiFetch('/api/dashboard/management').then(setManagement).catch(() => setManagement(demoManagement));
  }, [needsManagement, management]);

  useEffect(() => {
    window.localStorage.setItem(TAB_KEY, tab);
    setVisibleIds(loadLayout(role, tab));
  }, [tab, role]);

  const dashboard = data || demoDashboard;
  const failedSources = dashboard.failedDataSources || [];
  const hiddenWidgets = availableWidgets.filter(w => !widgetIds.includes(w.id));

  const persistAndSet = (next) => { setVisibleIds(next); saveLayout(role, tab, next); };
  const handleHide = (id) => persistAndSet(widgetIds.filter(w => w !== id));
  const handleAdd = (id) => { if (id) persistAndSet([...widgetIds, id]); };

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const handleDragEnd = ({ active, over }) => {
    if (!over || active.id === over.id) return;
    const oldIndex = widgetIds.indexOf(active.id);
    const newIndex = widgetIds.indexOf(over.id);
    if (oldIndex === -1 || newIndex === -1) return;
    persistAndSet(arrayMove(widgetIds, oldIndex, newIndex));
  };

  return (
    <div className="dashboard">
      <div className="page-heading">
        <div>
          <PageGreeting />
          <h1>Production Hub</h1>
        </div>
        {source === 'demo' && <span className="demo-badge">Demo data</span>}
        {source === 'unavailable' && <span className="demo-badge">Couldn't reach the API — showing sample data</span>}
      </div>

      {failedSources.length > 0 && (
        <div className="alert-banner">
          <span>
            ⚠ <strong>{failedSources.length} data source{failedSources.length === 1 ? '' : 's'}</strong> failed to sync — {failedSources.map(s => s.name).join(', ')}
          </span>
          <Link to="/data-sources">Go to Data Sources →</Link>
        </div>
      )}

      <div className="view-tabs production-hub-tabs">
        {TABS.map(t => (
          <button key={t.key} type="button" className={`view-tab ${tab === t.key ? 'active' : ''}`} onClick={() => setTab(t.key)}>
            {t.label}
          </button>
        ))}
      </div>

      <div className="dashboard-toolbar">
        <p className="panel-subtitle">Drag a widget's handle to rearrange it, or hide/add widgets below.</p>
        {hiddenWidgets.length > 0 && (
          <select
            className="dashboard-add-widget" value=""
            onChange={(event) => { handleAdd(event.target.value); event.target.value = ''; }}
          >
            <option value="">+ Add widget…</option>
            {hiddenWidgets.map(w => <option key={w.id} value={w.id}>{w.title}</option>)}
          </select>
        )}
      </div>

      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <SortableContext items={widgetIds} strategy={rectSortingStrategy}>
          <div className="dashboard-grid">
            {widgetIds.map((id) => {
              const widget = WIDGETS_BY_ID[id];
              if (!widget) return null;
              return (
                <SortableWidget key={id} id={id} size={widget.size} title={widget.title} demo={widget.demo} onHide={() => handleHide(id)}>
                  {widget.render(dashboard, role, management)}
                </SortableWidget>
              );
            })}
            {widgetIds.length === 0 && <p className="panel-subtitle">No widgets on this dashboard yet — add one above.</p>}
          </div>
        </SortableContext>
      </DndContext>
    </div>
  );
};

export default Dashboard;
