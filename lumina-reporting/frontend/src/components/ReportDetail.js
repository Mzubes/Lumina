import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { apiDownload, apiFetch, isDemoMode } from '../api';
import { ACTIONS_BY_STATUS, EXPORT_FORMATS, STATUS_LABEL } from './ReportsTable';
import WorkflowStepper from './charts/WorkflowStepper';

const REPORT_TYPE_LABEL = {
  factsheet: 'Factsheet', marketing: 'Marketing Material', performance: 'Performance Report',
  holdings: 'Holdings Report', pitchbook: 'Pitchbook', meeting_pack: 'Meeting Pack', custom: 'Custom',
};

const demoReport = {
  id: 0, title: 'July Performance Summary', client_id: 1, team: 'Institutional Sales',
  report_type: 'performance', status: 'review', template_id: null, complianceRequired: false,
  created_at: null,
};
const demoHistory = [
  { id: 1, from_status: 'draft', to_status: 'review', actor_email: 'editor@lumina.test', note: null, created_at: null },
];

const formatDate = (value) => (value ? new Date(value).toLocaleString() : '—');

const DocumentBlock = ({ component }) => {
  if (component.type === 'text_block') {
    return (
      <div className="document-block">
        <h3 className="document-block-title">{component.title}</h3>
        <p>{component.text}</p>
      </div>
    );
  }
  return (
    <div className="document-block">
      <h3 className="document-block-title">{component.title}</h3>
      <table className="data-table">
        <thead><tr>{component.columns.map(col => <th key={col}>{col}</th>)}</tr></thead>
        <tbody>
          {component.rows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {row.map((cell, cellIndex) => (
                <td key={cellIndex} className={cellIndex === 0 ? '' : 'num'}>
                  {typeof cell === 'number' ? cell.toLocaleString(undefined, { maximumFractionDigits: 2 }) : (cell || '—')}
                </td>
              ))}
            </tr>
          ))}
          {component.rows.length === 0 && (
            <tr><td colSpan={component.columns.length} className="reports-table-empty">No data for this section yet.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
};

const ReportDetail = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const role = window.localStorage.getItem('lumina_role') || '';

  const [report, setReport] = useState(null);
  const [clients, setClients] = useState([]);
  const [history, setHistory] = useState([]);
  const [content, setContent] = useState(null);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState('');
  const [flash, setFlash] = useState('');

  const loadReport = () => {
    if (isDemoMode) { setReport(demoReport); setHistory(demoHistory); return; }
    apiFetch(`/api/reports/${id}`).then(setReport).catch(() => setNotFound(true));
    if (role !== 'client') {
      apiFetch(`/api/reports/${id}/history`).then(setHistory).catch(() => setHistory([]));
    }
  };

  useEffect(loadReport, [id]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    // /api/clients is staff-only (a client user must never see the full client
    // list), so skip the call for the client role -- it would just 403.
    if (isDemoMode || role === 'client') return;
    apiFetch('/api/clients').then(setClients).catch(() => {});
  }, [role]);

  useEffect(() => {
    if (isDemoMode || !report || !report.template_id) { setContent(null); return; }
    apiFetch(`/api/reports/${report.id}/export?format=raw&raw_format=json`).then(setContent).catch(() => setContent(null));
  }, [report]);

  if (notFound) {
    return (
      <div className="report-detail">
        <button type="button" className="back-link" onClick={() => navigate(-1)}>← Back</button>
        <p className="form-message">Report not found, or you don't have access to it.</p>
      </div>
    );
  }
  if (!report) return <div className="report-detail" />;

  const clientName = clients.find(c => c.id === report.client_id)?.name || `Client #${report.client_id}`;
  const availableActions = (ACTIONS_BY_STATUS[report.status] || []).filter(({ roles }) => roles.includes(role));

  const handleAction = async (action) => {
    setError('');
    try {
      const updated = await apiFetch(`/api/reports/${report.id}/${action}`, { method: 'POST' });
      setReport(updated);
      setFlash(`Moved to ${STATUS_LABEL[updated.status] || updated.status}`);
      setTimeout(() => setFlash(''), 4000);
      if (role !== 'client') apiFetch(`/api/reports/${report.id}/history`).then(setHistory).catch(() => {});
    } catch (requestError) { setError(requestError.message); }
  };

  const handleExport = async (format) => {
    setError('');
    const query = format === 'raw' ? 'format=raw&raw_format=json' : `format=${format}`;
    try {
      await apiDownload(`/api/reports/${report.id}/export?${query}`);
    } catch (requestError) { setError(requestError.message); }
  };

  return (
    <div className="report-detail">
      <button type="button" className="back-link" onClick={() => navigate(-1)}>← Back</button>

      <div className="page-heading">
        <div>
          <span className="eyebrow">{REPORT_TYPE_LABEL[report.report_type] || 'Report'}</span>
          <h1>{report.title}</h1>
        </div>
        <span className={`status-badge status-${report.status}`}>{STATUS_LABEL[report.status] || report.status}</span>
      </div>

      <section className="panel report-detail-meta">
        <dl className="report-detail-fields">
          <div><dt>Client</dt><dd>{clientName}</dd></div>
          <div><dt>Team</dt><dd>{report.team || '—'}</dd></div>
          <div><dt>Created</dt><dd>{formatDate(report.created_at)}</dd></div>
          <div><dt>Last updated</dt><dd>{formatDate(report.updated_at)}</dd></div>
        </dl>
        <div className="report-detail-actions">
          {availableActions.map(({ action, label }) => (
            <button key={action} onClick={() => handleAction(action)}>{label}</button>
          ))}
          <select
            value="" onChange={(event) => { const format = event.target.value; if (format) handleExport(format); event.target.value = ''; }}
          >
            <option value="">Export as…</option>
            {EXPORT_FORMATS.map(({ value, label }) => (
              <option key={value} value={value} disabled={!report.template_id && value !== 'pdf'}>{label}</option>
            ))}
          </select>
        </div>
        {flash && <p className="form-message form-message-success">✓ {flash}</p>}
        {error && <p className="form-message">{error}</p>}
      </section>

      <section className="panel">
        <div className="panel-header"><h2>Workflow</h2></div>
        <WorkflowStepper status={report.status} complianceRequired={!!report.complianceRequired} />
      </section>

      <section className="panel">
        <div className="panel-header"><h2>Document preview</h2></div>
        {report.template_id ? (
          content ? (
            <div className="document-preview">
              {content.components.map((component, index) => <DocumentBlock component={component} key={index} />)}
              {content.components.length === 0 && <p className="panel-subtitle">This document has no content sections yet.</p>}
            </div>
          ) : <p className="panel-subtitle">Loading preview…</p>
        ) : (
          <p className="panel-subtitle">This report has no template, so there's no live preview — use Export → PDF to view it.</p>
        )}
      </section>

      {role !== 'client' && (
        <section className="panel">
          <div className="panel-header"><h2>History</h2></div>
          <ul className="timeline">
            {history.map(entry => (
              <li className="timeline-item" key={entry.id}>
                <div className="timeline-marker" />
                <div className="timeline-body">
                  <div className="timeline-transition">
                    {entry.from_status && <span className={`status-badge status-${entry.from_status}`}>{STATUS_LABEL[entry.from_status] || entry.from_status}</span>}
                    {entry.from_status && <span className="timeline-arrow">→</span>}
                    <span className={`status-badge status-${entry.to_status}`}>{STATUS_LABEL[entry.to_status] || entry.to_status}</span>
                  </div>
                  <div className="timeline-meta">{entry.actor_email} · {formatDate(entry.created_at)}</div>
                  {entry.note && <div className="timeline-note">“{entry.note}”</div>}
                </div>
              </li>
            ))}
            {history.length === 0 && <li className="timeline-empty">No workflow activity yet.</li>}
          </ul>
        </section>
      )}
    </div>
  );
};

export default ReportDetail;
