import React from 'react';

// Mirrors backend/risk_status.py's four statuses and their precedence. The
// status is always computed server-side; this file only decides how each one
// looks, so a new status added there renders as a plain neutral pill rather
// than disappearing.
export const RISK_LABELS = {
  sla_breached: { label: 'SLA breached', tone: 'critical' },
  flagged: { label: 'Flagged', tone: 'review' },
  watch: { label: 'Watch', tone: 'compliance' },
  on_track: { label: 'On track', tone: 'approved' },
};

const RiskBadge = ({ risk }) => {
  if (!risk?.status) return null;
  const meta = RISK_LABELS[risk.status] || { label: risk.status, tone: 'neutral' };
  return (
    // title carries the computed reason, so the badge explains itself on
    // hover without the row having to make space for a sentence.
    <span className={`risk-badge risk-${meta.tone}`} title={risk.reason || meta.label}>
      {meta.label}
    </span>
  );
};

export default RiskBadge;
