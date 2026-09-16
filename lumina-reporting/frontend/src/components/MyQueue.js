import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { apiFetch, fireReportAction, isDemoMode } from '../api';
import { getReportActions, StatusBadge } from './ReportsTable';

const demoQueue = [
  {
    id: 1, title: 'Q2 Institutional Portfolio Report', status: 'review', updated_at: null,
    reasons: [{ type: 'approval', label: 'Needs your approval' }],
  },
  {
    id: 2, title: 'Pzena Factsheet — Meridian Pension Partners', status: 'compliance', updated_at: null,
    reasons: [
      { type: 'compliance', label: 'Needs your compliance certification' },
      { type: 'component_review', label: '1 component needs your review', components: ['Portfolio Commentary'] },
    ],
  },
];

const REASON_ICON = { approval: '✓', compliance: '⚖', component_review: '§' };

// Time-in-stage rides on `updated_at` (bumped on every status transition)
// rather than a dedicated field -- no backend change needed for this.
const formatAge = (isoDate) => {
  if (!isoDate) return null;
  const days = Math.floor((Date.now() - new Date(isoDate).getTime()) / 86400000);
  if (days <= 0) return 'Entered this stage today';
  return `In this stage for ${days} day${days === 1 ? '' : 's'}`;
};

const MyQueue = () => {
  const role = window.localStorage.getItem('lumina_role') || '';
  const [queue, setQueue] = useState([]);
  const [error, setError] = useState('');

  const load = () => {
    if (isDemoMode) { setQueue(demoQueue); return; }
    apiFetch('/api/reports/my-queue').then(setQueue).catch(requestError => setError(requestError.message));
  };

  useEffect(load, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleAction = async (report, action) => {
    setError('');
    try {
      await fireReportAction(report.id, action);
      load();
    } catch (requestError) { setError(requestError.message); }
  };

  return (
    <div className="my-queue">
      <div className="page-heading">
        <div><span className="eyebrow">Task queue</span><h1>My Queue</h1></div>
        {isDemoMode && <span className="demo-badge">Demo data</span>}
      </div>
      <p className="panel-subtitle">
        Everything waiting on you, and why — approvals, compliance sign-offs, and component
        reviews assigned to you, all in one place.
      </p>

      {error && <p className="form-message">{error}</p>}

      <div className="queue-list">
        {queue.map((report) => {
          const actions = getReportActions(report, role);
          const age = formatAge(report.updated_at);
          return (
            <section className="panel queue-card" key={report.id}>
              <div className="queue-card-header">
                <div className="queue-card-title-group">
                  <Link to={`/reports/${report.id}`} className="reports-table-title-link queue-card-title">
                    {report.title}
                  </Link>
                  <div className="queue-card-meta">
                    <StatusBadge status={report.status} />
                    {age && <span className="queue-card-age">{age}</span>}
                  </div>
                </div>
                {actions.length > 0 && (
                  <div className="queue-card-actions">
                    {actions.map((actionItem) => (
                      <button
                        key={actionItem.key} type={actionItem.tone === 'neutral' ? undefined : 'button'}
                        className={actionItem.tone && actionItem.tone !== 'neutral' ? `action-btn tone-${actionItem.tone}` : undefined}
                        onClick={() => handleAction(report, actionItem)}
                      >
                        {actionItem.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <ul className="queue-reasons">
                {report.reasons.map((reason) => (
                  <li className={`queue-reason queue-reason-${reason.type}`} key={reason.type}>
                    <span className="queue-reason-icon">{REASON_ICON[reason.type] || '•'}</span>
                    {reason.type === 'component_review' ? (
                      <Link to={`/reports/${report.id}`}>
                        {reason.label}{reason.components && reason.components.length > 0 ? ` — ${reason.components.join(', ')}` : ''}
                      </Link>
                    ) : <span>{reason.label}</span>}
                  </li>
                ))}
              </ul>
            </section>
          );
        })}
        {queue.length === 0 && <p className="queue-empty">Nothing needs your attention right now.</p>}
      </div>
    </div>
  );
};

export default MyQueue;
