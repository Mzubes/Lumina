import React, { useEffect, useState } from 'react';
import { apiDownload, apiFetch, fireReportAction, isDemoMode } from '../api';
import ReportsTable, { statusBreakdown } from './ReportsTable';
import CompositionBar from './charts/CompositionBar';

const PACK_TYPES = { pitchbook: 'Pitch Book', meeting_pack: 'Meeting Pack' };

const demoPitchbooks = [
  { id: 4, title: 'Q3 Sales Pitch Book', client_id: 1, status: 'draft', team: 'Institutional Sales', report_type: 'pitchbook', created_at: null },
];

const newSlide = () => ({
  id: `slide-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
  type: 'text_block',
  title: '',
  staticText: '',
  reportId: '',
});

const toApiComponents = (slides) => slides.map((slide) => {
  if (slide.type === 'report_reference') {
    return { id: slide.id, type: 'report_reference', title: slide.title, data_binding: { report_id: Number(slide.reportId) } };
  }
  return { id: slide.id, type: 'text_block', title: slide.title, data_binding: { static_text: slide.staticText } };
});

const Pitchbooks = () => {
  const [reports, setReports] = useState([]);
  const [error, setError] = useState('');
  const role = window.localStorage.getItem('lumina_role') || '';
  const canCreate = ['admin', 'editor'].includes(role);

  const [clients, setClients] = useState([]);
  const [facets, setFacets] = useState({ teams: [] });
  const [clientReports, setClientReports] = useState([]);

  const [form, setForm] = useState({ title: '', client_id: '', team: '', report_type: 'pitchbook' });
  const [slides, setSlides] = useState([newSlide()]);
  const [formMessage, setFormMessage] = useState('');

  const loadReports = () => {
    if (isDemoMode) { setReports(demoPitchbooks); return; }
    apiFetch('/api/reports')
      .then(all => setReports(all.filter(r => r.report_type === 'pitchbook' || r.report_type === 'meeting_pack')))
      .catch(() => setReports(demoPitchbooks));
  };

  useEffect(loadReports, []);

  useEffect(() => {
    if (isDemoMode) return;
    apiFetch('/api/clients').then(setClients).catch(() => {});
    apiFetch('/api/reports/facets').then(setFacets).catch(() => {});
  }, []);

  useEffect(() => {
    if (isDemoMode || !form.client_id) { setClientReports([]); return; }
    apiFetch(`/api/reports?client_id=${form.client_id}`)
      .then(all => setClientReports(all.filter(r => r.template_id && r.report_type !== 'pitchbook' && r.report_type !== 'meeting_pack')))
      .catch(() => setClientReports([]));
  }, [form.client_id]);

  const resetForm = () => {
    setForm({ title: '', client_id: '', team: '', report_type: 'pitchbook' });
    setSlides([newSlide()]);
  };

  const updateSlide = (index, patch) => {
    setSlides(rows => rows.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  };
  const addSlide = () => setSlides(rows => [...rows, newSlide()]);
  const removeSlide = (index) => setSlides(rows => rows.filter((_, i) => i !== index));
  const moveSlide = (index, direction) => {
    setSlides((rows) => {
      const target = index + direction;
      if (target < 0 || target >= rows.length) return rows;
      const next = [...rows];
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  };

  const handleAction = async (report, action) => {
    setError('');
    try {
      await fireReportAction(report.id, action);
      loadReports();
    } catch (requestError) { setError(requestError.message); }
  };

  const handleExport = async (report, format) => {
    setError('');
    const query = format === 'raw' ? 'format=raw&raw_format=json' : `format=${format}`;
    try {
      await apiDownload(`/api/reports/${report.id}/export?${query}`);
    } catch (requestError) { setError(requestError.message); }
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setFormMessage('');
    try {
      const template = await apiFetch('/api/templates', {
        method: 'POST',
        body: JSON.stringify({
          name: `${form.title} — deck`,
          description: `Slide deck backing "${form.title}"`,
          components: toApiComponents(slides),
        }),
      });
      await apiFetch('/api/reports', {
        method: 'POST',
        body: JSON.stringify({
          title: form.title,
          client_id: Number(form.client_id),
          team: form.team || undefined,
          report_type: form.report_type,
          template_id: template.id,
        }),
      });
      resetForm();
      loadReports();
    } catch (requestError) { setFormMessage(requestError.message); }
  };

  return (
    <div className="pitchbooks">
      <div className="page-heading">
        <div><span className="eyebrow">Production</span><h1>Pitch Books &amp; Meeting Packs</h1></div>
        {isDemoMode && <span className="demo-badge">Demo data</span>}
      </div>

      {canCreate && (
        <section className="panel">
          <h2>Assemble a deck</h2>
          <form onSubmit={handleSubmit}>
            <label>Title
              <input value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} required />
            </label>
            <label>Client
              <select value={form.client_id} onChange={e => setForm({ ...form, client_id: e.target.value })} required>
                <option value="">Choose a client…</option>
                {clients.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </label>
            <label>Team
              <input
                value={form.team} onChange={e => setForm({ ...form, team: e.target.value })}
                list="pitchbook-team-suggestions" placeholder="e.g. Institutional Sales"
              />
              <datalist id="pitchbook-team-suggestions">
                {facets.teams.map(team => <option key={team} value={team} />)}
              </datalist>
            </label>
            <label>Type
              <select value={form.report_type} onChange={e => setForm({ ...form, report_type: e.target.value })}>
                {Object.entries(PACK_TYPES).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </label>

            <h3>Slides</h3>
            <p className="panel-subtitle">
              Build the deck slide by slide. Pull in an existing fact sheet or report, or write a custom slide of your own.
              {!form.client_id && ' Choose a client above to browse their existing content.'}
            </p>
            {slides.map((slide, index) => (
              <div className="component-row" key={slide.id}>
                <div className="component-row-header">
                  <select value={slide.type} onChange={e => updateSlide(index, { type: e.target.value })}>
                    <option value="text_block">Custom text slide</option>
                    <option value="report_reference">Insert existing report</option>
                  </select>
                  <input
                    placeholder="Slide title"
                    value={slide.title}
                    onChange={e => updateSlide(index, { title: e.target.value })}
                  />
                  <button type="button" onClick={() => moveSlide(index, -1)} disabled={index === 0}>↑</button>
                  <button type="button" onClick={() => moveSlide(index, 1)} disabled={index === slides.length - 1}>↓</button>
                  <button type="button" onClick={() => removeSlide(index)}>Remove</button>
                </div>

                {slide.type === 'text_block' && (
                  <textarea
                    placeholder="Slide content"
                    value={slide.staticText}
                    onChange={e => updateSlide(index, { staticText: e.target.value })}
                  />
                )}

                {slide.type === 'report_reference' && (
                  <select value={slide.reportId} onChange={e => updateSlide(index, { reportId: e.target.value })} required>
                    <option value="">Choose a report to pull in…</option>
                    {clientReports.map(r => <option key={r.id} value={r.id}>{r.title}</option>)}
                  </select>
                )}
              </div>
            ))}
            <button type="button" onClick={addSlide}>Add a slide</button>

            <div className="form-actions">
              <button type="submit">Create deck</button>
            </div>
          </form>
          {formMessage && <p className="form-message">{formMessage}</p>}
        </section>
      )}

      {reports.length > 0 && (
        <section className="panel">
          <div className="panel-header"><h2>Status mix</h2></div>
          <CompositionBar title="Status mix" data={statusBreakdown(reports)} />
        </section>
      )}

      <section className="panel">
        <div className="panel-header"><h2>Pitch books &amp; meeting packs</h2></div>
        <ReportsTable
          reports={reports} role={role} onAction={handleAction} onExport={handleExport}
          emptyMessage="No pitch books or meeting packs yet."
        />
      </section>
      {error && <p className="form-message">{error}</p>}
    </div>
  );
};

export default Pitchbooks;
