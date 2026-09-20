import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { apiFetch, isDemoMode } from '../api';
import PageGreeting from './PageGreeting';
import { IconCheckCircle, IconClipboard, IconDocument, IconWorkflow } from '../icons';

const demoTriage = {
  respondingCount: 14, stuckCount: 6, overdueCount: 7, readyToDistributeCount: 9, staleAfterDays: 3,
};

// `count` is the key on the API payload, so a card can never drift from the
// number it claims to show.
const CARDS = [
  {
    key: 'respondingCount', title: "What I'm responsible for", icon: IconClipboard,
    description: "Reports where you're the next action.", to: '/queue',
    unit: (n) => `${n} waiting on you`,
  },
  {
    key: 'stuckCount', title: 'Where things are stuck', icon: IconWorkflow,
    description: (data) => `No movement in ${data.staleAfterDays ?? 3}+ days.`, to: '/reports?stuck=1',
    unit: (n) => `${n} flagged`,
  },
  {
    key: 'overdueCount', title: 'Overdue reports', icon: IconDocument,
    description: 'Past their due date and still open.', to: '/reports?overdue=1',
    unit: (n) => `${n} overdue`,
  },
  {
    key: 'readyToDistributeCount', title: 'Ready to distribute', icon: IconCheckCircle,
    description: 'Approved and one click from sending.', to: '/queue',
    unit: (n) => `${n} ready`,
  },
];

const StaffTriage = () => {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (isDemoMode) { setData(demoTriage); return; }
    apiFetch('/api/triage').then(setData).catch(requestError => setError(requestError.message));
  }, []);

  return (
    <div className="staff-triage">
      <div className="staff-triage-hero">
        <div className="staff-triage-mark">L</div>
        <PageGreeting variant="hero" />
        <p className="staff-triage-subtitle">Where would you like to start today?</p>
        {isDemoMode && <span className="demo-badge">Demo data</span>}
      </div>

      {error && <p className="form-message">{error}</p>}

      <div className="staff-triage-grid">
        {CARDS.map(({ key, title, icon: Icon, description, to, unit }) => (
          <Link key={key} to={to} className="staff-triage-card">
            <span className="staff-triage-card-icon"><Icon /></span>
            <h2>{title}</h2>
            <p>{typeof description === 'function' ? description(data || {}) : description}</p>
            {/* No placeholder zero before the counts land -- a card that says
                "0 waiting on you" and then changes to 14 has lied once. */}
            <span className="staff-triage-count">{data ? unit(data[key] ?? 0) : '—'}</span>
          </Link>
        ))}
      </div>
    </div>
  );
};

export default StaffTriage;
