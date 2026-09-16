import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { apiFetch, isDemoMode } from '../api';

const demoEvents = [
  {
    type: 'transition', report_id: 1, report_title: 'Q2 Institutional Portfolio Report',
    summary: 'draft → review', actor_email: 'editor@lumina.test', created_at: null,
  },
  {
    type: 'component_review', report_id: 2, report_title: 'Pzena Factsheet — Meridian Pension Partners',
    summary: 'Reviewed "Portfolio Commentary"', actor_email: 'compliance@lumina.test', created_at: null,
  },
  {
    type: 'distribution_link', report_id: 2, report_title: 'Pzena Factsheet — Meridian Pension Partners',
    summary: 'Created a distribution link for Dana Whitfield', actor_email: 'admin@lumina.test', created_at: null,
  },
];

const TYPE_LABEL = { transition: 'Workflow', component_review: 'Review', distribution_link: 'Distribution' };

const formatDate = (value) => (value ? new Date(value).toLocaleString() : '—');

const ActivityLog = () => {
  const [events, setEvents] = useState([]);
  const [error, setError] = useState('');

  useEffect(() => {
    if (isDemoMode) { setEvents(demoEvents); return; }
    apiFetch('/api/activity').then(setEvents).catch(requestError => setError(requestError.message));
  }, []);

  return (
    <div className="activity-log">
      <div className="page-heading">
        <div><span className="eyebrow">Admin</span><h1>Activity Log</h1></div>
        {isDemoMode && <span className="demo-badge">Demo data</span>}
      </div>
      <p className="panel-subtitle">
        Every workflow transition, component review, and distribution link across the firm, newest first.
      </p>

      {error && <p className="form-message">{error}</p>}

      <section className="panel">
        <ul className="timeline">
          {events.map((event, index) => (
            <li className="timeline-item" key={index}>
              <div className="timeline-marker" />
              <div className="timeline-body">
                <div className="timeline-transition">
                  <Link to={`/reports/${event.report_id}`} className="reports-table-title-link">{event.report_title}</Link>
                  <span className={`activity-type-badge activity-type-${event.type}`}>{TYPE_LABEL[event.type] || event.type}</span>
                </div>
                <div className="timeline-summary">{event.summary}</div>
                <div className="timeline-meta">{event.actor_email} · {formatDate(event.created_at)}</div>
              </div>
            </li>
          ))}
          {events.length === 0 && <li className="timeline-empty">No activity yet.</li>}
        </ul>
      </section>
    </div>
  );
};

export default ActivityLog;
