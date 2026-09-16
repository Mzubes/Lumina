import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { DndContext, KeyboardSensor, PointerSensor, closestCenter, useSensor, useSensors } from '@dnd-kit/core';
import { SortableContext, arrayMove, rectSortingStrategy, sortableKeyboardCoordinates, useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { apiFetch, isDemoMode } from '../api';
import { DEFAULT_LAYOUT, WIDGETS_BY_ID, widgetsForRole } from './dashboardWidgets';

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
};

const layoutKey = (role) => `lumina_dashboard_layout_${role || 'viewer'}`;

const loadLayout = (role) => {
  try {
    const raw = window.localStorage.getItem(layoutKey(role));
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed.visible)) return parsed.visible;
    }
  } catch { /* corrupt/blocked storage -- fall through to defaults */ }
  return DEFAULT_LAYOUT[role] || DEFAULT_LAYOUT.viewer || [];
};

const saveLayout = (role, visible) => {
  try { window.localStorage.setItem(layoutKey(role), JSON.stringify({ visible })); } catch { /* per-viewer convenience only */ }
};

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

// Derived from the real logged-in email's local-part (e.g. 'admin' from
// 'admin@lumina.test') rather than a fabricated display name -- there's no
// separate name field on User yet, and this reads naturally as a greeting
// without inventing data.
const displayNameFromEmail = (email) => {
  const localPart = (email || '').split('@')[0];
  if (!localPart) return null;
  return localPart.charAt(0).toUpperCase() + localPart.slice(1);
};

const Dashboard = () => {
  const role = window.localStorage.getItem('lumina_role') || 'viewer';
  const displayName = displayNameFromEmail(window.localStorage.getItem('lumina_email'));

  const [data, setData] = useState(null);
  // 'live' | 'demo' | 'unavailable' -- distinct from isDemoMode, so a real
  // fetch failure never gets silently presented as though it were real data.
  const [source, setSource] = useState(isDemoMode ? 'demo' : 'live');
  const [visibleIds, setVisibleIds] = useState(() => loadLayout(role));

  useEffect(() => {
    if (isDemoMode) { setData(demoDashboard); return; }
    apiFetch('/api/dashboard')
      .then(payload => { setData(payload); setSource('live'); })
      .catch(() => { setData(demoDashboard); setSource('unavailable'); });
  }, []);

  const dashboard = data || demoDashboard;
  const failedSources = dashboard.failedDataSources || [];

  const availableWidgets = widgetsForRole(role);
  const availableIds = new Set(availableWidgets.map(w => w.id));
  const widgetIds = visibleIds.filter(id => availableIds.has(id) && WIDGETS_BY_ID[id]);
  const hiddenWidgets = availableWidgets.filter(w => !widgetIds.includes(w.id));

  const persistAndSet = (next) => { setVisibleIds(next); saveLayout(role, next); };
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
          <span className="eyebrow">Overview</span>
          <h1>{displayName ? `Welcome back, ${displayName}` : 'Reporting dashboard'}</h1>
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
                  {widget.render(dashboard, role)}
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
