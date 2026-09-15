import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { apiDownload, apiFetch, apiFetchBlobUrl, isDemoMode } from '../api';
import DistributionPanel from './DistributionPanel';
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

const ReportDetail = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const role = window.localStorage.getItem('lumina_role') || '';

  const [report, setReport] = useState(null);
  const [clients, setClients] = useState([]);
  const [funds, setFunds] = useState([]);
  const [history, setHistory] = useState([]);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [previewError, setPreviewError] = useState('');
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
    apiFetch('/api/funds').then(setFunds).catch(() => {});
  }, [role]);

  useEffect(() => {
    // The preview IS the generated PDF -- fetched as a blob and handed to an
    // <iframe>, so what's shown at every workflow stage is exactly the file
    // that ships, not a lookalike rendering of the same data.
    if (isDemoMode || !report || !report.template_id) { setPreviewUrl(null); return; }
    let cancelled = false;
    let objectUrl = null;
    setPreviewError('');
    apiFetchBlobUrl(`/api/reports/${report.id}/export?format=pdf`).then(url => {
      if (cancelled) { window.URL.revokeObjectURL(url); return; }
      objectUrl = url;
      setPreviewUrl(url);
    }).catch(requestError => { if (!cancelled) setPreviewError(requestError.message); });
    return () => {
      cancelled = true;
      if (objectUrl) window.URL.revokeObjectURL(objectUrl);
    };
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

  const clientName = report.client_id
    ? (clients.find(c => c.id === report.client_id)?.name || `Client #${report.client_id}`)
    : null;
  const fundName = report.fund_id
    ? (funds.find(f => f.id === report.fund_id)?.name || `Fund #${report.fund_id}`)
    : null;
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
        <div className="report-detail-header-actions">
          {availableActions.map(({ action, label, tone }) => (
            <button
              key={action} type={tone === 'neutral' ? undefined : 'button'}
              className={`action-btn-lg ${tone && tone !== 'neutral' ? `action-btn tone-${tone}` : ''}`}
              onClick={() => handleAction(action)}
            >
              {label}
            </button>
          ))}
          <span className={`status-badge status-${report.status}`}>{STATUS_LABEL[report.status] || report.status}</span>
        </div>
      </div>

      {flash && <p className="form-message form-message-success">✓ {flash}</p>}
      {error && <p className="form-message">{error}</p>}

      <div className="report-detail-layout">
        <div className="report-detail-main">
          <section className="panel">
            <div className="panel-header"><h2>Workflow</h2></div>
            <WorkflowStepper status={report.status} complianceRequired={!!report.complianceRequired} />
          </section>

          <section className="panel">
            <div className="panel-header">
              <h2>Document preview</h2>
              <span className="panel-header-note">Showing the live, generated PDF</span>
            </div>
            {report.template_id ? (
              previewUrl ? (
                <iframe src={previewUrl} title="Document preview" className="document-preview-frame" />
              ) : previewError ? (
                <p className="form-message">{previewError}</p>
              ) : <p className="panel-subtitle">Generating preview…</p>
            ) : (
              <p className="panel-subtitle">This report has no template, so there's no live preview — use Export → PDF to view it.</p>
            )}
          </section>
        </div>

        <div className="report-detail-sidebar">
          <section className="panel">
            <div className="panel-header"><h2>Request details</h2></div>
            <dl className="report-detail-fields">
              <div><dt>{clientName ? 'Client' : 'Fund / Strategy'}</dt><dd>{clientName || fundName || '—'}</dd></div>
              <div><dt>Team</dt><dd>{report.team || '—'}</dd></div>
              <div><dt>Compliance required</dt><dd>{report.complianceRequired ? 'Yes' : 'No'}</dd></div>
              <div><dt>Created</dt><dd>{formatDate(report.created_at)}</dd></div>
              <div><dt>Last updated</dt><dd>{formatDate(report.updated_at)}</dd></div>
            </dl>
            <select
              className="report-detail-export"
              value="" onChange={(event) => { const format = event.target.value; if (format) handleExport(format); event.target.value = ''; }}
            >
              <option value="">Export as…</option>
              {EXPORT_FORMATS.map(({ value, label }) => (
                <option key={value} value={value} disabled={!report.template_id && value !== 'pdf'}>{label}</option>
              ))}
            </select>
          </section>

          {role !== 'client' && report.status === 'distributed' && (
            <DistributionPanel reportId={report.id} clientId={report.client_id} role={role} />
          )}

          {role !== 'client' && (
            <section className="panel">
              <div className="panel-header"><h2>Activity</h2></div>
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
      </div>
    </div>
  );
};

export default ReportDetail;
