import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { apiDownload, apiFetch, isDemoMode } from '../api';
import useLuminaAsk from '../useLuminaAsk';
import AssistantReply from './AssistantReply';
import { IconSparkle } from '../icons';

// Mirrors ACTION_TYPES in backend/routes/activity.py. An action type the
// backend adds later renders with its raw key and a neutral tone rather
// than vanishing, so the trail never silently hides an event.
const ACTION_TYPES = [
  { value: '', label: 'All actions' },
  { value: 'created', label: 'Created', tone: 'draft' },
  { value: 'workflow', label: 'Workflow', tone: 'neutral' },
  { value: 'content', label: 'Content', tone: 'compliance' },
  { value: 'compliance', label: 'Compliance', tone: 'review' },
  { value: 'sign_off', label: 'Sign-off', tone: 'approved' },
  { value: 'distribution', label: 'Distributed', tone: 'distributed' },
  { value: 'rejected', label: 'Rejected', tone: 'critical' },
];
const TONE_BY_TYPE = Object.fromEntries(ACTION_TYPES.filter(t => t.value).map(t => [t.value, t]));

const demoEvents = [
  {
    reference: 'REF-T4821', type: 'transition', actionType: 'distribution',
    created_at: '2026-09-18T14:02:00', actor_email: 'rmorgan@lumina.test',
    report_id: 1, report_title: 'Pzena Q3 Factsheet', target: 'Pzena Q3 Factsheet',
    summary: 'approved → Distributed',
  },
  {
    reference: 'REF-C102', type: 'component_review', actionType: 'content',
    created_at: '2026-09-18T11:40:00', actor_email: 'jdoe@lumina.test',
    report_id: 1, report_title: 'Pzena Q3 Factsheet', target: 'Performance table',
    summary: 'Reviewed "Performance table"',
  },
];

const EMPTY_FILTERS = { report_id: '', actor: '', action_type: '', since: '', until: '' };

const buildQuery = (filters) => {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => { if (value) params.set(key, value); });
  const query = params.toString();
  return query ? `?${query}` : '';
};

const formatTimestamp = (iso) => {
  if (!iso) return '—';
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString();
};

const ActionPill = ({ actionType }) => {
  const meta = TONE_BY_TYPE[actionType] || { label: actionType, tone: 'neutral' };
  return <span className={`action-pill action-${meta.tone}`}>{meta.label}</span>;
};

// The same assistant as the corner panel, embedded where an auditor is
// already looking. It shares useLuminaAsk with the FAB, so both go through
// one request path; this one just isn't a floating panel.
const AuditConsole = () => {
  const [draft, setDraft] = useState('');
  const { messages, sending, error, contextSummary, ask } = useLuminaAsk();

  const send = (text) => {
    if (!text || sending) return;
    setDraft('');
    ask(text, { page: 'Audit Trail' });
  };

  const submit = (event) => { event.preventDefault(); send(draft.trim()); };

  return (
    <section className="panel audit-console">
      <div className="audit-console-head">
        <IconSparkle />
        <div>
          <h2>Ask about this trail</h2>
          <p className="panel-subtitle">
            Read-only. Lumina AI can explain what happened and point you at records; it can't
            change, approve, or remove anything in the trail.
          </p>
        </div>
      </div>

      {messages.length > 0 && (
        <div className="audit-console-messages">
          {messages.map((message, index) => (
            message.role === 'assistant'
              ? <AssistantReply key={index} message={message} onFollowUp={send} />
              : <div key={index} className="lumina-ai-bubble lumina-ai-bubble-user">{message.text}</div>
          ))}
          {sending && <div className="lumina-ai-bubble lumina-ai-bubble-assistant lumina-ai-thinking">Thinking…</div>}
        </div>
      )}
      {contextSummary && (
        <div className="lumina-ai-chips">
          {contextSummary.split(' · ').map(chip => <span key={chip} className="lumina-ai-chip">{chip}</span>)}
        </div>
      )}
      {error && <p className="form-message">{error}</p>}

      <form className="lumina-ai-input-row" onSubmit={submit}>
        <input
          type="text" placeholder="e.g. Which reports went out without a compliance step?"
          value={draft} onChange={event => setDraft(event.target.value)} disabled={sending}
        />
        <button type="submit" className="btn btn-primary" disabled={sending || !draft.trim()}>Ask</button>
      </form>
    </section>
  );
};

const AuditTrail = () => {
  const [events, setEvents] = useState([]);
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [error, setError] = useState('');
  const [exportMessage, setExportMessage] = useState('');

  useEffect(() => {
    if (isDemoMode) { setEvents(demoEvents); return; }
    apiFetch(`/api/activity${buildQuery(filters)}`)
      .then(setEvents)
      .catch(requestError => setError(requestError.message));
  }, [filters]);

  const update = (key, value) => setFilters(current => ({ ...current, [key]: value }));
  const filtersActive = Object.values(filters).some(Boolean);

  const handleExport = async () => {
    setExportMessage('');
    try {
      // Same query params as the list above, so the file and the screen can
      // never disagree about what was exported.
      await apiDownload(`/api/activity/export${buildQuery(filters)}`);
    } catch (requestError) { setExportMessage(requestError.message); }
  };

  return (
    <div className="audit-trail">
      <div className="page-heading">
        <div><span className="eyebrow">Admin</span><h1>Audit Trail</h1></div>
        {isDemoMode && <span className="demo-badge">Demo data</span>}
      </div>
      <p className="panel-subtitle">
        Every workflow move, content review and distribution link on record, newest first. Each
        row carries a stable reference you can cite; nothing here can be edited or removed.
      </p>

      <AuditConsole />

      {error && <p className="form-message">{error}</p>}

      <section className="panel">
        <div className="filter-bar">
          <div className="filter-pills">
            {ACTION_TYPES.map(type => (
              <button
                key={type.value || 'all'} type="button"
                className={`filter-pill ${filters.action_type === type.value ? 'active' : ''}`}
                onClick={() => update('action_type', type.value)}
              >
                {type.label}
              </button>
            ))}
          </div>
          <input
            className="filter-search" type="search" placeholder="Actor email…"
            value={filters.actor} onChange={event => update('actor', event.target.value)}
          />
          <input
            className="filter-select" type="number" min="1" placeholder="Report ID"
            value={filters.report_id} onChange={event => update('report_id', event.target.value)}
          />
          <label className="filter-date">From
            <input type="date" value={filters.since} onChange={event => update('since', event.target.value)} />
          </label>
          <label className="filter-date">To
            <input type="date" value={filters.until} onChange={event => update('until', event.target.value)} />
          </label>
          {filtersActive && (
            <button type="button" className="filter-clear" onClick={() => setFilters(EMPTY_FILTERS)}>Clear filters</button>
          )}
          <button type="button" onClick={handleExport}>Export audit package (CSV)</button>
        </div>
        {exportMessage && <p className="form-message">{exportMessage}</p>}

        <div className="audit-table">
          <div className="audit-row audit-row-head">
            <span>Reference</span><span>When</span><span>Action</span>
            <span>Actor</span><span>Target</span><span>Detail</span>
          </div>
          {events.map(event => (
            <div className="audit-row" key={event.reference}>
              <span className="audit-reference">{event.reference}</span>
              <span className="audit-when">{formatTimestamp(event.created_at)}</span>
              <span><ActionPill actionType={event.actionType} /></span>
              <span className="audit-actor">{event.actor_email || 'System'}</span>
              <span className="audit-target">
                <Link to={`/reports/${event.report_id}`}>{event.report_title}</Link>
                {event.target !== event.report_title && <span className="book-perf-sub"> · {event.target}</span>}
              </span>
              <span className="audit-detail">{event.summary}</span>
            </div>
          ))}
          {events.length === 0 && (
            <p className="field-hint">
              {filtersActive ? 'No events match these filters.' : 'Nothing has happened yet.'}
            </p>
          )}
        </div>
      </section>
    </div>
  );
};

export default AuditTrail;
