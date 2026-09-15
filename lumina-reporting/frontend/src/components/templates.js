import React, { useEffect, useState } from 'react';
import {
  DndContext, DragOverlay, KeyboardSensor, PointerSensor,
  closestCenter, pointerWithin, useDraggable, useDroppable, useSensor, useSensors,
} from '@dnd-kit/core';
import { SortableContext, arrayMove, sortableKeyboardCoordinates, useSortable, verticalListSortingStrategy } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { apiFetch, isDemoMode } from '../api';
import { PRESETS_BY_ID, TEMPLATE_LIBRARY } from './templateLibrary';
import WorkflowCanvas from './workflowEditor/WorkflowCanvas';

const COMPONENT_TYPES = [
  { value: 'holdings_table', label: 'Holdings Table' },
  { value: 'performance_summary', label: 'Performance Summary' },
  { value: 'text_block', label: 'Commentary Text' },
  { value: 'data_table', label: 'Data Table (custom)' },
  { value: 'people_grid', label: 'People / Bios' },
  { value: 'report_reference', label: 'Referenced Report' },
];
const TYPE_LABELS = Object.fromEntries(COMPONENT_TYPES.map(t => [t.value, t.label]));

const PERIOD_TYPES = ['MTD', 'QTD', 'YTD', '1Y', 'ITD'];

const CHART_TYPES = [
  { value: 'none', label: 'None (table only)' },
  { value: 'bar_comparison', label: 'Bar comparison (col 2 vs. col 3)' },
];

const REVIEW_ROLES = [
  { value: '', label: 'No review required' },
  { value: 'compliance', label: 'Compliance' },
  { value: 'admin', label: 'Admin' },
  { value: 'editor', label: 'Editor' },
];

const makeComponentId = () => `comp-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;

const newComponent = () => ({
  id: makeComponentId(),
  type: 'holdings_table',
  title: '',
  periodTypes: ['QTD', 'YTD'],
  staticText: '',
  tableColumns: ['Metric', 'Value'],
  tableRows: [['', '']],
  chartType: 'none',
  people: [{ name: '', title: '', detail: '', photoUrl: '' }],
  reviewRole: '',
  reportId: '',
});

const componentPreview = (component) => {
  switch (component.type) {
    case 'text_block':
      if (!component.staticText) return 'No text yet';
      return component.staticText.length > 90 ? `${component.staticText.slice(0, 90)}…` : component.staticText;
    case 'data_table': {
      const chart = component.chartType && component.chartType !== 'none' ? ' · chart' : '';
      return `${component.tableColumns.length} column${component.tableColumns.length === 1 ? '' : 's'} × ${component.tableRows.length} row${component.tableRows.length === 1 ? '' : 's'}${chart}`;
    }
    case 'people_grid': {
      const names = component.people.filter(p => p.name).map(p => p.name);
      return names.length ? names.join(', ') : 'No people yet';
    }
    case 'holdings_table':
      return 'Data-driven — latest holdings on file';
    case 'performance_summary':
      return `Data-driven — ${component.periodTypes.length ? component.periodTypes.join(', ') : 'no periods selected'}`;
    case 'report_reference':
      return component.reportId ? `References report #${component.reportId}` : 'No report selected';
    default:
      return '';
  }
};

const toApiComponents = (components) => components.map((component) => {
  const base = { id: component.id, type: component.type, title: component.title, review_role: component.reviewRole || undefined };
  if (component.type === 'text_block') {
    return { ...base, data_binding: { static_text: component.staticText } };
  }
  if (component.type === 'performance_summary') {
    return { ...base, data_binding: { dataset: 'performance', filters: { period_types: component.periodTypes } } };
  }
  if (component.type === 'data_table') {
    return { ...base, data_binding: { columns: component.tableColumns, rows: component.tableRows, chart_type: component.chartType || 'none' } };
  }
  if (component.type === 'people_grid') {
    return {
      ...base,
      data_binding: { rows: component.people.map(p => ({ name: p.name, title: p.title, detail: p.detail, photo_url: p.photoUrl || undefined })) },
    };
  }
  if (component.type === 'report_reference') {
    return { ...base, data_binding: { report_id: component.reportId ? Number(component.reportId) : undefined } };
  }
  return { ...base, data_binding: { dataset: 'holdings', filters: { as_of: 'latest' } } };
});

const fromApiComponents = (apiComponents) => apiComponents.map((component) => ({
  id: component.id,
  type: component.type,
  title: component.title,
  periodTypes: (component.data_binding && component.data_binding.filters && component.data_binding.filters.period_types) || ['QTD', 'YTD'],
  staticText: (component.data_binding && component.data_binding.static_text) || '',
  tableColumns: (component.data_binding && component.data_binding.columns) || ['Metric', 'Value'],
  tableRows: (component.data_binding && component.data_binding.rows) || [['', '']],
  chartType: (component.data_binding && component.data_binding.chart_type) || 'none',
  people: ((component.data_binding && component.data_binding.rows) || [{ name: '', title: '', detail: '', photoUrl: '' }])
    .map(p => ({ name: p.name || '', title: p.title || '', detail: p.detail || '', photoUrl: p.photo_url || '' })),
  reviewRole: component.review_role || '',
  reportId: (component.data_binding && component.data_binding.report_id) || '',
}));

const collisionDetectionStrategy = (args) => {
  const pointerCollisions = pointerWithin(args);
  return pointerCollisions.length > 0 ? pointerCollisions : closestCenter(args);
};

const LibraryCard = ({ preset, onAdd }) => {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: `palette-${preset.id}`, data: { source: 'palette', presetId: preset.id },
  });
  return (
    <div ref={setNodeRef} className={`library-preset-card ${isDragging ? 'is-dragging' : ''}`} {...attributes} {...listeners}>
      <div className="library-preset-card-body">
        <strong>{preset.label}</strong>
        <span>{preset.description}</span>
      </div>
      <button type="button" className="library-preset-add-btn" onClick={(event) => { event.stopPropagation(); onAdd(); }}>
        +
      </button>
    </div>
  );
};

const CanvasCard = ({ component, isExpanded, onToggle, onRemove, children }) => {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: component.id });
  const style = { transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.4 : 1 };

  return (
    <div ref={setNodeRef} style={style} className={`canvas-card ${isExpanded ? 'is-expanded' : ''} ${isDragging ? 'is-dragging' : ''}`}>
      <div className="canvas-card-header" onClick={onToggle}>
        <button type="button" className="canvas-card-drag-handle" onClick={(e) => e.stopPropagation()} {...attributes} {...listeners}>⠿</button>
        <span className="canvas-card-type-badge">{TYPE_LABELS[component.type] || component.type}</span>
        <div className="canvas-card-title-group">
          <span className="canvas-card-title">{component.title || 'Untitled section'}</span>
          <span className="canvas-card-preview">{componentPreview(component)}</span>
        </div>
        {component.reviewRole && <span className="canvas-card-review-badge">{component.reviewRole}</span>}
        <button type="button" className="canvas-card-remove" onClick={(e) => { e.stopPropagation(); onRemove(); }}>Remove</button>
        <span className="canvas-card-chevron">{isExpanded ? '▾' : '▸'}</span>
      </div>
      {isExpanded && <div className="canvas-card-body">{children}</div>}
    </div>
  );
};

const Templates = () => {
  const [templates, setTemplates] = useState([]);
  const [disclosures, setDisclosures] = useState([]);
  const [clients, setClients] = useState([]);
  const [assignedClientIds, setAssignedClientIds] = useState([]);
  const [flash, setFlash] = useState('');
  const [error, setError] = useState('');
  const [editingId, setEditingId] = useState(null);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [components, setComponents] = useState(() => [newComponent()]);
  const [expandedId, setExpandedId] = useState(() => components[0]?.id ?? null);
  const [settingsOpen, setSettingsOpen] = useState(true);
  const [activeDrag, setActiveDrag] = useState(null);
  const [selectedDisclosureIds, setSelectedDisclosureIds] = useState([]);
  const [headerTitle, setHeaderTitle] = useState('');
  const [headerSubtitle, setHeaderSubtitle] = useState('');
  const [footerText, setFooterText] = useState('');
  const [primaryColor, setPrimaryColor] = useState('');
  const [accentColor, setAccentColor] = useState('');
  const [logoUrl, setLogoUrl] = useState('');

  const { setNodeRef: setCanvasDropRef, isOver: isCanvasOver } = useDroppable({ id: 'canvas-dropzone' });
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const loadTemplates = () => {
    if (isDemoMode) return;
    apiFetch('/api/templates').then(setTemplates).catch(requestError => setError(requestError.message));
  };

  useEffect(() => {
    if (isDemoMode) return;
    loadTemplates();
    apiFetch('/api/disclosures').then(setDisclosures).catch(() => {});
    apiFetch('/api/clients').then(setClients).catch(() => {});
  }, []);

  const resetForm = () => {
    setEditingId(null);
    setName('');
    setDescription('');
    const starter = newComponent();
    setComponents([starter]);
    setExpandedId(starter.id);
    setSettingsOpen(true);
    setSelectedDisclosureIds([]);
    setHeaderTitle('');
    setHeaderSubtitle('');
    setFooterText('');
    setPrimaryColor('');
    setAccentColor('');
    setLogoUrl('');
    setAssignedClientIds([]);
  };

  const startEdit = (template) => {
    setEditingId(template.id);
    setName(template.name);
    setDescription(template.description || '');
    setComponents(fromApiComponents(template.components));
    setExpandedId(null);
    setSettingsOpen(false);
    setSelectedDisclosureIds(template.disclosure_ids || []);
    setHeaderTitle((template.header_config && template.header_config.title) || '');
    setHeaderSubtitle((template.header_config && template.header_config.subtitle) || '');
    setFooterText((template.footer_config && template.footer_config.text) || '');
    setPrimaryColor((template.theme_config && template.theme_config.primary_color) || '');
    setAccentColor((template.theme_config && template.theme_config.accent_color) || '');
    setLogoUrl((template.theme_config && template.theme_config.logo_url) || '');
    apiFetch(`/api/templates/${template.id}/clients`).then(setAssignedClientIds).catch(() => setAssignedClientIds([]));
  };

  const updateComponent = (index, patch) => {
    setComponents(rows => rows.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  };
  const removeComponent = (index) => setComponents(rows => rows.filter((_, i) => i !== index));

  const insertPreset = (preset, atIndex) => {
    const newRow = { id: makeComponentId(), ...preset.buildDefault() };
    setComponents((rows) => {
      const next = [...rows];
      next.splice(atIndex === undefined ? next.length : atIndex, 0, newRow);
      return next;
    });
    setExpandedId(newRow.id);
  };

  const togglePeriod = (index, period) => {
    setComponents(rows => rows.map((row, i) => {
      if (i !== index) return row;
      const has = row.periodTypes.includes(period);
      return { ...row, periodTypes: has ? row.periodTypes.filter(p => p !== period) : [...row.periodTypes, period] };
    }));
  };

  const updateTableColumn = (index, colIndex, value) => {
    setComponents(rows => rows.map((row, i) => (i === index
      ? { ...row, tableColumns: row.tableColumns.map((c, ci) => (ci === colIndex ? value : c)) } : row)));
  };
  const addTableColumn = (index) => {
    setComponents(rows => rows.map((row, i) => (i === index ? {
      ...row,
      tableColumns: [...row.tableColumns, `Column ${row.tableColumns.length + 1}`],
      tableRows: row.tableRows.map(r => [...r, '']),
    } : row)));
  };
  const removeTableColumn = (index) => {
    setComponents(rows => rows.map((row, i) => (i === index && row.tableColumns.length > 1 ? {
      ...row,
      tableColumns: row.tableColumns.slice(0, -1),
      tableRows: row.tableRows.map(r => r.slice(0, -1)),
    } : row)));
  };
  const updateTableCell = (index, rowIndex, cellIndex, value) => {
    setComponents(rows => rows.map((row, i) => (i === index ? {
      ...row,
      tableRows: row.tableRows.map((r, ri) => (ri === rowIndex ? r.map((c, ci) => (ci === cellIndex ? value : c)) : r)),
    } : row)));
  };
  const addTableRow = (index) => {
    setComponents(rows => rows.map((row, i) => (i === index
      ? { ...row, tableRows: [...row.tableRows, row.tableColumns.map(() => '')] } : row)));
  };
  const removeTableRow = (index, rowIndex) => {
    setComponents(rows => rows.map((row, i) => (i === index
      ? { ...row, tableRows: row.tableRows.filter((_, ri) => ri !== rowIndex) } : row)));
  };

  const updatePerson = (index, personIndex, field, value) => {
    setComponents(rows => rows.map((row, i) => (i === index
      ? { ...row, people: row.people.map((p, pi) => (pi === personIndex ? { ...p, [field]: value } : p)) } : row)));
  };
  const addPerson = (index) => {
    setComponents(rows => rows.map((row, i) => (i === index
      ? { ...row, people: [...row.people, { name: '', title: '', detail: '' }] } : row)));
  };
  const removePerson = (index, personIndex) => {
    setComponents(rows => rows.map((row, i) => (i === index
      ? { ...row, people: row.people.filter((_, pi) => pi !== personIndex) } : row)));
  };

  const toggleDisclosure = (disclosureId) => {
    setSelectedDisclosureIds(current => (current.includes(disclosureId)
      ? current.filter(id => id !== disclosureId) : [...current, disclosureId]));
  };

  const toggleAssignedClient = (clientId) => {
    setAssignedClientIds(current => (current.includes(clientId)
      ? current.filter(id => id !== clientId) : [...current, clientId]));
  };

  const handleSaveAssignedClients = async () => {
    setError('');
    try {
      await apiFetch(`/api/templates/${editingId}/clients`, {
        method: 'PUT', body: JSON.stringify({ client_ids: assignedClientIds }),
      });
      setFlash('Assigned clients saved.');
      setTimeout(() => setFlash(''), 4000);
    } catch (requestError) { setError(requestError.message); }
  };

  const handleApprove = async () => {
    if (!window.confirm( // eslint-disable-line no-alert
      'Approving generates one new draft report for every assigned client, right now. Continue?',
    )) return;
    setError('');
    try {
      const result = await apiFetch(`/api/templates/${editingId}/approve`, { method: 'POST' });
      setFlash(`Approved — generated ${result.generated_reports.length} report(s).`);
      setTimeout(() => setFlash(''), 6000);
      loadTemplates();
    } catch (requestError) { setError(requestError.message); }
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    const payload = {
      name, description, components: toApiComponents(components),
      disclosure_ids: selectedDisclosureIds,
      header_config: (headerTitle || headerSubtitle) ? { title: headerTitle, subtitle: headerSubtitle } : null,
      footer_config: footerText ? { text: footerText } : null,
      theme_config: (primaryColor || accentColor || logoUrl)
        ? { primary_color: primaryColor || undefined, accent_color: accentColor || undefined, logo_url: logoUrl || undefined } : null,
    };
    try {
      if (editingId) {
        await apiFetch(`/api/templates/${editingId}`, { method: 'PUT', body: JSON.stringify(payload) });
      } else {
        await apiFetch('/api/templates', { method: 'POST', body: JSON.stringify(payload) });
      }
      resetForm();
      loadTemplates();
    } catch (requestError) { setError(requestError.message); }
  };

  const handleDelete = async (templateId) => {
    setError('');
    try {
      await apiFetch(`/api/templates/${templateId}`, { method: 'DELETE' });
      loadTemplates();
    } catch (requestError) { setError(requestError.message); }
  };

  const handleDragStart = ({ active }) => {
    if (active.data.current?.source === 'palette') {
      setActiveDrag({ kind: 'palette', preset: PRESETS_BY_ID[active.data.current.presetId] });
    } else {
      setActiveDrag({ kind: 'canvas', component: components.find(c => c.id === active.id) });
    }
  };

  const handleDragEnd = ({ active, over }) => {
    setActiveDrag(null);
    if (!over) return;
    if (active.data.current?.source === 'palette') {
      const preset = PRESETS_BY_ID[active.data.current.presetId];
      if (!preset) return;
      const overIndex = components.findIndex(c => c.id === over.id);
      insertPreset(preset, overIndex === -1 ? components.length : overIndex);
      return;
    }
    const oldIndex = components.findIndex(c => c.id === active.id);
    const newIndex = components.findIndex(c => c.id === over.id);
    if (oldIndex !== -1 && newIndex !== -1 && oldIndex !== newIndex) {
      setComponents(rows => arrayMove(rows, oldIndex, newIndex));
    }
  };

  const handleDragCancel = () => setActiveDrag(null);

  return (
    <div className="templates">
      <div className="page-heading">
        <div><span className="eyebrow">Report design</span><h1>Templates</h1></div>
        {isDemoMode && <span className="demo-badge">Demo data</span>}
      </div>

      <section className="panel">
        <h2>Templates</h2>
        <ul className="report-list">
          {templates.map(template => (
            <li key={template.id}>
              <span>{template.name}</span>
              <button type="button" onClick={() => startEdit(template)}>Edit</button>
              <button type="button" onClick={() => handleDelete(template.id)}>Delete</button>
            </li>
          ))}
          {templates.length === 0 && <li>No templates yet.</li>}
        </ul>
      </section>

      <section className="panel">
        <h2>{editingId ? 'Edit template' : 'New template'}</h2>
        <form onSubmit={handleSubmit}>
          <button type="button" className="document-settings-toggle" onClick={() => setSettingsOpen(open => !open)}>
            {settingsOpen ? '▾' : '▸'} Document settings
          </button>
          {settingsOpen && (
            <div className="document-settings-body">
              <label>Name
                <input value={name} onChange={e => setName(e.target.value)} required />
              </label>
              <label>Description
                <input value={description} onChange={e => setDescription(e.target.value)} />
              </label>

              <h3>Header &amp; footer</h3>
              <p className="field-hint">Shown at the top and bottom of every page when exported to PDF. Leave blank for no repeating banner.</p>
              <label>Header title
                <input placeholder="e.g. ACME GLOBAL EQUITY STRATEGY" value={headerTitle} onChange={e => setHeaderTitle(e.target.value)} />
              </label>
              <label>Header subtitle
                <input placeholder="e.g. As of June 30, 2026 | For Professional Investors Only" value={headerSubtitle} onChange={e => setHeaderSubtitle(e.target.value)} />
              </label>
              <label>Footer text
                <input placeholder="e.g. Acme Asset Management | (800) 555-0100 | acme.com" value={footerText} onChange={e => setFooterText(e.target.value)} />
              </label>

              <h3>Theme</h3>
              <p className="field-hint">Colors the PDF's header banner, section titles, table headers, and any charts. Leave blank for a plain, colorless document.</p>
              <div className="theme-fields-row">
                <label>Primary color
                  <input type="color" value={primaryColor || '#0d6b5f'} onChange={e => setPrimaryColor(e.target.value)} />
                </label>
                <label>Accent color
                  <input type="color" value={accentColor || '#c9bd9a'} onChange={e => setAccentColor(e.target.value)} />
                </label>
              </div>
              <label>Logo URL
                <input placeholder="https://... or a data: URI" value={logoUrl} onChange={e => setLogoUrl(e.target.value)} />
              </label>
            </div>
          )}

          <h3>Sections</h3>
          <DndContext
            sensors={sensors} collisionDetection={collisionDetectionStrategy}
            onDragStart={handleDragStart} onDragEnd={handleDragEnd} onDragCancel={handleDragCancel}
          >
            <div className="template-builder-layout">
              <aside className="component-library">
                {TEMPLATE_LIBRARY.map(group => (
                  <div className="library-category" key={group.category}>
                    <h4>{group.category}</h4>
                    {group.presets.map(preset => (
                      <LibraryCard key={preset.id} preset={preset} onAdd={() => insertPreset(preset)} />
                    ))}
                  </div>
                ))}
              </aside>

              <div className="template-canvas">
                <SortableContext items={components.map(c => c.id)} strategy={verticalListSortingStrategy}>
                  {components.map((component, index) => (
                    <CanvasCard
                      key={component.id}
                      component={component}
                      isExpanded={expandedId === component.id}
                      onToggle={() => setExpandedId(current => (current === component.id ? null : component.id))}
                      onRemove={() => removeComponent(index)}
                    >
                      <div className="canvas-card-fields">
                        <label>Type
                          <select value={component.type} onChange={e => updateComponent(index, { type: e.target.value })}>
                            {COMPONENT_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                          </select>
                        </label>
                        <label>Title
                          <input placeholder="Section title" value={component.title} onChange={e => updateComponent(index, { title: e.target.value })} />
                        </label>
                        <label>Requires review from
                          <select value={component.reviewRole || ''} onChange={e => updateComponent(index, { reviewRole: e.target.value })}>
                            {REVIEW_ROLES.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
                          </select>
                        </label>
                      </div>

                      {component.type === 'performance_summary' && (
                        <div className="period-checkboxes">
                          {PERIOD_TYPES.map(period => (
                            <label key={period} className="checkbox-label">
                              <input
                                type="checkbox"
                                checked={component.periodTypes.includes(period)}
                                onChange={() => togglePeriod(index, period)}
                              /> {period}
                            </label>
                          ))}
                        </div>
                      )}

                      {component.type === 'text_block' && (
                        <textarea
                          placeholder="Commentary text"
                          value={component.staticText}
                          onChange={e => updateComponent(index, { staticText: e.target.value })}
                        />
                      )}

                      {component.type === 'report_reference' && (
                        <label>Referenced report ID
                          <input
                            type="number" placeholder="e.g. 42" value={component.reportId}
                            onChange={e => updateComponent(index, { reportId: e.target.value })}
                          />
                        </label>
                      )}

                      {component.type === 'data_table' && (
                        <div className="data-table-editor">
                          <label className="chart-type-label">Chart
                            <select value={component.chartType || 'none'} onChange={e => updateComponent(index, { chartType: e.target.value })}>
                              {CHART_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                            </select>
                          </label>
                          <div className="data-table-editor-row data-table-editor-columns">
                            {component.tableColumns.map((col, colIndex) => (
                              <input
                                key={colIndex} placeholder={`Column ${colIndex + 1}`} value={col}
                                onChange={e => updateTableColumn(index, colIndex, e.target.value)}
                              />
                            ))}
                            <button type="button" onClick={() => addTableColumn(index)}>+ Column</button>
                            <button type="button" onClick={() => removeTableColumn(index)} disabled={component.tableColumns.length <= 1}>− Column</button>
                          </div>
                          {component.tableRows.map((row, rowIndex) => (
                            <div className="data-table-editor-row" key={rowIndex}>
                              {row.map((cell, cellIndex) => (
                                <input
                                  key={cellIndex} value={cell}
                                  onChange={e => updateTableCell(index, rowIndex, cellIndex, e.target.value)}
                                />
                              ))}
                              <button type="button" onClick={() => removeTableRow(index, rowIndex)} disabled={component.tableRows.length <= 1}>Remove row</button>
                            </div>
                          ))}
                          <button type="button" onClick={() => addTableRow(index)}>+ Row</button>
                        </div>
                      )}

                      {component.type === 'people_grid' && (
                        <div className="people-grid-editor">
                          {component.people.map((person, personIndex) => (
                            <div className="people-grid-editor-row" key={personIndex}>
                              <input placeholder="Name" value={person.name} onChange={e => updatePerson(index, personIndex, 'name', e.target.value)} />
                              <input placeholder="Title" value={person.title} onChange={e => updatePerson(index, personIndex, 'title', e.target.value)} />
                              <input placeholder="Detail" value={person.detail} onChange={e => updatePerson(index, personIndex, 'detail', e.target.value)} />
                              <input placeholder="Photo URL (optional)" value={person.photoUrl} onChange={e => updatePerson(index, personIndex, 'photoUrl', e.target.value)} />
                              <button type="button" onClick={() => removePerson(index, personIndex)} disabled={component.people.length <= 1}>Remove</button>
                            </div>
                          ))}
                          <button type="button" onClick={() => addPerson(index)}>+ Person</button>
                        </div>
                      )}
                    </CanvasCard>
                  ))}
                </SortableContext>
                <div ref={setCanvasDropRef} className={`canvas-dropzone ${isCanvasOver ? 'is-over' : ''}`}>
                  {components.length === 0 ? 'Drag a component here to get started' : 'Drop here to add to the end'}
                </div>
              </div>
            </div>

            <DragOverlay>
              {activeDrag?.kind === 'palette' && (
                <div className="library-preset-card is-overlay"><strong>{activeDrag.preset.label}</strong></div>
              )}
              {activeDrag?.kind === 'canvas' && activeDrag.component && (
                <div className="canvas-card is-overlay">
                  <div className="canvas-card-header">
                    <span className="canvas-card-type-badge">{TYPE_LABELS[activeDrag.component.type]}</span>
                    <span className="canvas-card-title">{activeDrag.component.title || 'Untitled section'}</span>
                  </div>
                </div>
              )}
            </DragOverlay>
          </DndContext>

          <h3>Disclosures</h3>
          <p className="field-hint">Selected disclosures are appended to the end of the document, in this order.</p>
          <div className="disclosure-picker">
            {disclosures.map(disclosure => (
              <label key={disclosure.id} className="checkbox-label">
                <input
                  type="checkbox"
                  checked={selectedDisclosureIds.includes(disclosure.id)}
                  onChange={() => toggleDisclosure(disclosure.id)}
                /> {disclosure.title}
              </label>
            ))}
            {disclosures.length === 0 && <p className="field-hint">No disclosures in the library yet — add some on the Disclosures page.</p>}
          </div>

          <div className="form-actions">
            <button type="submit">{editingId ? 'Save changes' : 'Create template'}</button>
            {editingId && <button type="button" onClick={resetForm}>Cancel</button>}
          </div>
        </form>
      </section>

      {editingId && (() => {
        const activeTemplate = templates.find(t => t.id === editingId);
        return (
          <section className="panel">
            <h2>Assigned clients &amp; approval</h2>
            <p className="field-hint">
              Approving generates one draft report per assigned client, immediately — each one then moves
              through the normal Draft → Review → Compliance → Approved → Distributed workflow on its own.
            </p>
            <div className="disclosure-picker">
              {clients.map(clientOption => (
                <label key={clientOption.id} className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={assignedClientIds.includes(clientOption.id)}
                    onChange={() => toggleAssignedClient(clientOption.id)}
                  /> {clientOption.name}
                </label>
              ))}
              {clients.length === 0 && <p className="field-hint">No clients yet — add some on the Clients page.</p>}
            </div>
            <div className="form-actions">
              <button type="button" onClick={handleSaveAssignedClients}>Save assigned clients</button>
              <button type="button" onClick={handleApprove}>Approve &amp; Generate</button>
            </div>
            <p className="field-hint">
              {activeTemplate && activeTemplate.approved_at
                ? `Approved ${new Date(activeTemplate.approved_at).toLocaleString()}`
                : 'Not yet approved.'}
            </p>
          </section>
        );
      })()}

      {editingId && (
        <section className="panel">
          <h2>Workflow</h2>
          <p className="field-hint">
            How a report built from this template moves from draft to distribution -- firm-defined steps, assigned
            to a workflow group or left generic, with parallel branches where more than one team needs to sign off
            at once. New templates use the standard Draft → Review → Approved → Distributed pipeline until you
            customize it here.
          </p>
          <WorkflowCanvas templateId={editingId} />
        </section>
      )}

      {flash && <p className="form-message form-message-success">✓ {flash}</p>}
      {error && <p className="form-message">{error}</p>}
    </div>
  );
};

export default Templates;
