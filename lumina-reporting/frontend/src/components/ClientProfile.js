import React, { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { apiFetch, isDemoMode } from '../api';
import { askLumina } from '../luminaAskBus';
import Avatar from './Avatar';
import RiskBadge from './RiskBadge';
import { StatusBadge } from './ReportsTable';
import { money, pct } from './InternalPortal';

// Deliberately no "Transactions" tab. No transaction model exists anywhere
// in the schema, and a tab that renders invented trades on a client record
// is worse than no tab. It can be added once there's a real source to bind.
//
// "Risk" isn't a tab either -- it's one computed status and one reason
// sentence, which belong in the header where they're always visible rather
// than hidden behind a click.
const TABS = [
  { key: 'performance', label: 'Performance' },
  { key: 'holdings', label: 'Holdings' },
  { key: 'reports', label: 'Reports & Documents' },
];

const demoProfile = {
  client: { id: 1, name: 'Meridian Pension Partners', contact_email: 'ops@meridian.example' },
  relationshipManager: 'rmorgan@lumina.test',
  risk: { status: 'watch', reason: 'YTD return of 6.9% trails its 8.1% benchmark.' },
  aum: 612000000, asOfDate: '2026-06-30',
  holdings: [], performance: [], reports: [],
};

const ClientProfile = () => {
  const { id } = useParams();
  const [profile, setProfile] = useState(null);
  const [error, setError] = useState('');
  const [tab, setTab] = useState('performance');

  useEffect(() => {
    if (isDemoMode) { setProfile(demoProfile); return; }
    setProfile(null);
    apiFetch(`/api/book/${id}`).then(setProfile).catch(requestError => setError(requestError.message));
  }, [id]);

  if (error) {
    return (
      <div className="client-profile">
        <p className="form-message">{error}</p>
        <Link className="btn-link" to="/internal-portal">← Back to the Internal Portal</Link>
      </div>
    );
  }
  if (!profile) return <p className="field-hint">Loading…</p>;

  const { client, holdings = [], performance = [], reports = [] } = profile;

  return (
    <div className="client-profile">
      <Link className="btn-link" to="/internal-portal">← Internal Portal</Link>

      <div className="client-profile-header">
        <Avatar name={client.name} />
        <div className="client-profile-identity">
          <h1>{client.name}</h1>
          <p className="panel-subtitle">
            {client.contact_email || 'No contact email on file'}
            {' · '}
            {profile.relationshipManager ? `Managed by ${profile.relationshipManager}` : 'No relationship manager assigned'}
          </p>
        </div>
        <RiskBadge risk={profile.risk} />
      </div>

      {profile.risk && profile.risk.status !== 'on_track' && (
        <div className="alert-banner"><span>⚠ {profile.risk.reason}</span></div>
      )}

      <div className="metric-grid">
        <article className="metric-card">
          <div className="metric-tile-header"><span className="metric-tile-label">AUM</span></div>
          <strong>{money(profile.aum)}</strong>
          {profile.asOfDate && <span className="metric-tile-prev">As of {profile.asOfDate}</span>}
        </article>
        <article className="metric-card">
          <div className="metric-tile-header"><span className="metric-tile-label">Holdings on file</span></div>
          <strong>{holdings.length}</strong>
        </article>
        <article className="metric-card">
          <div className="metric-tile-header"><span className="metric-tile-label">Reports on file</span></div>
          <strong>{reports.length}</strong>
        </article>
        <article className="metric-card">
          <div className="metric-tile-header"><span className="metric-tile-label">Ask Lumina AI</span></div>
          <button
            type="button"
            onClick={() => askLumina(
              `Give me a briefing on ${client.name} — recent performance, where their reporting stands, and anything I should raise with them.`,
              { clientId: client.id },
            )}
          >
            Brief me on this account
          </button>
        </article>
      </div>

      <section className="panel">
        <div className="view-tabs">
          {TABS.map(option => (
            <button
              key={option.key} type="button"
              className={`view-tab ${tab === option.key ? 'active' : ''}`}
              onClick={() => setTab(option.key)}
            >
              {option.label}
            </button>
          ))}
        </div>

        {tab === 'performance' && (
          performance.length === 0
            ? <p className="field-hint">No performance snapshots on file.</p>
            : (
              <table className="scorecard-table">
                <thead><tr><th>Period</th><th>Return</th><th>Benchmark</th><th>Difference</th></tr></thead>
                <tbody>
                  {performance.map(snapshot => {
                    const hasBoth = snapshot.return_pct != null && snapshot.benchmark_return_pct != null;
                    const diff = hasBoth ? snapshot.return_pct - snapshot.benchmark_return_pct : null;
                    return (
                      <tr key={snapshot.id}>
                        <td>{snapshot.period_type}</td>
                        <td>{pct(snapshot.return_pct)}</td>
                        <td>{pct(snapshot.benchmark_return_pct)}</td>
                        {/* Only shown where both sides exist -- a difference
                            against a missing benchmark isn't a difference. */}
                        <td className={diff == null ? '' : diff < 0 ? 'book-perf-down' : 'book-perf-up'}>
                          {diff == null ? '—' : pct(diff)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )
        )}

        {tab === 'holdings' && (
          holdings.length === 0
            ? <p className="field-hint">No holdings on file.</p>
            : (
              <table className="scorecard-table">
                <thead><tr><th>Security</th><th>Weight</th><th>Market value</th></tr></thead>
                <tbody>
                  {holdings.map(holding => (
                    <tr key={holding.id}>
                      <td>{holding.security_name || holding.security_id}</td>
                      <td>{holding.weight_pct != null ? `${holding.weight_pct.toFixed(1)}%` : '—'}</td>
                      <td>{holding.market_value != null ? money(Number(holding.market_value)) : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )
        )}

        {tab === 'reports' && (
          reports.length === 0
            ? <p className="field-hint">No reports yet.</p>
            : (
              <ul className="book-holdings-list">
                {reports.map(report => (
                  <li key={report.id}>
                    <Link to={`/reports/${report.id}`}>{report.title}</Link>
                    <StatusBadge status={report.status} />
                  </li>
                ))}
              </ul>
            )
        )}
      </section>
    </div>
  );
};

export default ClientProfile;
