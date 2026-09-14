import React, { useEffect, useState } from 'react';
import { apiFetch, isDemoMode } from '../api';

const COMPONENT_TYPES = [
  { value: 'holdings_table', label: 'Holdings Table' },
  { value: 'performance_summary', label: 'Performance Summary' },
  { value: 'text_block', label: 'Commentary Text' },
];

const PERIOD_TYPES = ['MTD', 'QTD', 'YTD', '1Y', 'ITD'];

const newComponent = () => ({
  id: `comp-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
  type: 'holdings_table',
  title: '',
  periodTypes: ['QTD', 'YTD'],
  staticText: '',
});

const toApiComponents = (components) => components.map((component) => {
  if (component.type === 'text_block') {
    return { id: component.id, type: component.type, title: component.title, data_binding: { static_text: component.staticText } };
  }
  if (component.type === 'performance_summary') {
    return {
      id: component.id, type: component.type, title: component.title,
      data_binding: { dataset: 'performance', filters: { period_types: component.periodTypes } },
    };
  }
  return {
    id: component.id, type: component.type, title: component.title,
    data_binding: { dataset: 'holdings', filters: { as_of: 'latest' } },
  };
});

const fromApiComponents = (apiComponents) => apiComponents.map((component) => ({
  id: component.id,
  type: component.type,
  title: component.title,
  periodTypes: (component.data_binding && component.data_binding.filters && component.data_binding.filters.period_types) || ['QTD', 'YTD'],
  staticText: (component.data_binding && component.data_binding.static_text) || '',
}));

const Templates = () => {
  const [templates, setTemplates] = useState([]);
  const [error, setError] = useState('');
  const [editingId, setEditingId] = useState(null);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [components, setComponents] = useState([newComponent()]);

  const loadTemplates = () => {
    if (isDemoMode) return;
    apiFetch('/api/templates').then(setTemplates).catch(requestError => setError(requestError.message));
  };

  useEffect(() => { if (!isDemoMode) loadTemplates(); }, []);

  const resetForm = () => {
    setEditingId(null);
    setName('');
    setDescription('');
    setComponents([newComponent()]);
  };

  const startEdit = (template) => {
    setEditingId(template.id);
    setName(template.name);
    setDescription(template.description || '');
    setComponents(fromApiComponents(template.components));
  };

  const updateComponent = (index, patch) => {
    setComponents(rows => rows.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  };
  const addComponent = () => setComponents(rows => [...rows, newComponent()]);
  const removeComponent = (index) => setComponents(rows => rows.filter((_, i) => i !== index));
  const moveComponent = (index, direction) => {
    setComponents((rows) => {
      const target = index + direction;
      if (target < 0 || target >= rows.length) return rows;
      const next = [...rows];
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  };
  const togglePeriod = (index, period) => {
    setComponents(rows => rows.map((row, i) => {
      if (i !== index) return row;
      const has = row.periodTypes.includes(period);
      return { ...row, periodTypes: has ? row.periodTypes.filter(p => p !== period) : [...row.periodTypes, period] };
    }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    const payload = { name, description, components: toApiComponents(components) };
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
          <label>Name
            <input value={name} onChange={e => setName(e.target.value)} required />
          </label>
          <label>Description
            <input value={description} onChange={e => setDescription(e.target.value)} />
          </label>

          <h3>Sections</h3>
          {components.map((component, index) => (
            <div className="component-row" key={component.id}>
              <div className="component-row-header">
                <select value={component.type} onChange={e => updateComponent(index, { type: e.target.value })}>
                  {COMPONENT_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
                <input
                  placeholder="Section title"
                  value={component.title}
                  onChange={e => updateComponent(index, { title: e.target.value })}
                />
                <button type="button" onClick={() => moveComponent(index, -1)} disabled={index === 0}>↑</button>
                <button type="button" onClick={() => moveComponent(index, 1)} disabled={index === components.length - 1}>↓</button>
                <button type="button" onClick={() => removeComponent(index)}>Remove</button>
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
            </div>
          ))}
          <button type="button" onClick={addComponent}>Add a section</button>

          <div className="form-actions">
            <button type="submit">{editingId ? 'Save changes' : 'Create template'}</button>
            {editingId && <button type="button" onClick={resetForm}>Cancel</button>}
          </div>
        </form>
      </section>

      {error && <p className="form-message">{error}</p>}
    </div>
  );
};

export default Templates;
