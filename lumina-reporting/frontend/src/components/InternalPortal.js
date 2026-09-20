import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { apiFetch, isDemoMode } from '../api';
import { askLumina } from '../luminaAskBus';
import Avatar from './Avatar';
import RiskBadge from './RiskBadge';
import { StatusBadge } from './ReportsTable';

const demoBook = {
  scope: 'firm',
  totalAum: 2840000000,
  clientCount: 4,
  underperformingCount: 1,
  reportsDeliveredMtd: 2,
  clients: [
    {
      client: { id: 1, name: 'Meridian Pension Partners', contact_email: 'ops@meridian.example' },
      relationshipManager: 'rmorgan@lumina.test',
      risk: { status: 'on_track', reason: 'No open deadlines at risk.' },
      aum: 612000000, asOfDate: '2026-06-30',
      performance: { periodType: 'YTD', returnPct: 9.4, benchmarkReturnPct: 8.1, isUnderperforming: false },
      lastReport: { id: 1, title: 'Pzena Q3 Factsheet', status: 'distributed', isDistributed: true },
    },
    {
      client: { id: 2, name: 'Northbridge Capital Partners', contact_email: 'ir@northbridge.example' },
      relationshipManager: null,
      risk: { status: 'watch', reason: 'YTD return of 6.9% trails its 8.1% benchmark.' },
      aum: 488000000, asOfDate: '2026-06-30',
      performance: { periodType: 'YTD', returnPct: 6.9, benchmarkReturnPct: 8.1, isUnderperforming: true },
      lastReport: { id: 2, title: 'Northbridge Monthly', status: 'review', isDistributed: false },
    },
  ],
};

export const money = (value) => {
  if (value === null || value === undefined) return '—';
  if (value >= 1e9) return `$${(value / 1e9).toFixed(2)}B`;
  if (value >= 1e6) return `$${(value / 1e6).toFixed(1)}M`;
  if (value >= 1e3) return `$${(value / 1e3).toFixed(0)}K`;
  return `$${value.toFixed(0)}`;
};

export const pct = (value) => (value === null || value === undefined ? '—' : `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`);

// Two flat modes, not a hierarchy: the model records one RM per client and
// nothing about who manages whom, so anything deeper would be invented.
const SCOPES = [
  { key: 'firm', label: 'Whole firm' },
  { key: 'mine', label: 'Just my clients' },
];

const InternalPortal = () => {
  const [book, setBook] = useState(null);
  const [error, setError] = useState('');
  const [scope, setScope] = useState('firm');
  const [search, setSearch] = useState('');
  const [expandedId, setExpandedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    if (isDemoMode) { setBook({ ...demoBook, scope }); return; }
    setBook(null);
    setExpandedId(null);
    setDetail(null);
    apiFetch(`/api/book${scope === 'mine' ? '?scope=mine' : ''}`)
      .then(setBook)
      .catch(requestError => setError(requestError.message));
  }, [scope]);

  // Client-side over the already-fetched rows -- the book is one page of
  // clients, so a round trip per keystroke would buy nothing.
  const visibleClients = useMemo(() => {
    const rows = book?.clients || [];
    const needle = search.trim().toLowerCase();
    if (!needle) return rows;
    return rows.filter(row =>
      row.client.name.toLowerCase().includes(needle)
      || (row.client.contact_email || '').toLowerCase().includes(needle)
      || (row.relationshipManager || '').toLowerCase().includes(needle));
  }, [book, search]);

  const toggleRow = (clientId) => {
    if (expandedId === clientId) { setExpandedId(null); setDetail(null); return; }
    setExpandedId(clientId);
    setDetail(null);
    if (isDemoMode) return;
    setDetailLoading(true);
    apiFetch(`/api/book/${clientId}`).then(setDetail).catch(requestError => setError(requestError.message)).finally(() => setDetailLoading(false));
  };

  const scopedNoun = book?.scope === 'mine' ? 'your clients' : "your firm's book";

  return (
    <div className="internal-portal">
      <div className="page-heading">
        <div><span className="eyebrow">Client Hub</span><h1>Internal Portal</h1></div>
        {isDemoMode && <span className="demo-badge">Demo data</span>}
      </div>
      <p className="panel-subtitle">
        {scopedNoun[0].toUpperCase() + scopedNoun.slice(1)} at a glance — AUM, performance against
        benchmark, delivery risk, and the most recent report for every client — or drill into one
        for its full holdings and history.
      </p>

      {error && <p className="form-message">{error}</p>}

      {book && (
        <div className="metric-grid">
          <article className="metric-card">
            <div className="metric-tile-header"><span className="metric-tile-label">Total AUM</span></div>
            <strong>{money(book.totalAum)}</strong>
          </article>
          <article className="metric-card">
            <div className="metric-tile-header"><span className="metric-tile-label">Clients</span></div>
            <strong>{book.clientCount}</strong>
          </article>
          <article className="metric-card">
            <div className="metric-tile-header"><span className="metric-tile-label">Trailing benchmark</span></div>
            <strong>{book.underperformingCount}</strong>
          </article>
          <article className="metric-card">
            <div className="metric-tile-header"><span className="metric-tile-label">Reports delivered (MTD)</span></div>
            <strong>{book.reportsDeliveredMtd}</strong>
          </article>
        </div>
      )}

      <section className="panel">
        <div className="book-toolbar">
          <div className="view-tabs">
            {SCOPES.map(option => (
              <button
                key={option.key} type="button"
                className={`view-tab ${scope === option.key ? 'active' : ''}`}
                onClick={() => setScope(option.key)}
              >
                {option.label}
              </button>
            ))}
          </div>
          <input
            className="filter-search" type="search" placeholder="Search clients…"
            value={search} onChange={event => setSearch(event.target.value)}
          />
        </div>

        <div className="book-table">
          <div className="book-row book-row-head">
            <span>Client</span><span>Relationship manager</span><span>AUM</span>
            <span>Performance</span><span>Status</span><span>Last report</span><span />
          </div>
          {visibleClients.map((row) => (
            <React.Fragment key={row.client.id}>
              <div
                className={`book-row book-row-body ${expandedId === row.client.id ? 'is-open' : ''}`}
                onClick={() => toggleRow(row.client.id)}
              >
                <span className="book-client-cell">
                  <Avatar name={row.client.name} />
                  <span className="book-client-name">{row.client.name}</span>
                </span>
                {/* Unassigned is said out loud rather than left blank -- a
                    client with no RM is a gap someone should close. */}
                <span className={row.relationshipManager ? '' : 'book-perf-sub'}>
                  {row.relationshipManager || 'Unassigned'}
                </span>
                <span>{money(row.aum)}</span>
                <span>
                  {row.performance ? (
                    <>
                      <span className={row.performance.isUnderperforming ? 'book-perf-down' : 'book-perf-up'}>
                        {pct(row.performance.returnPct)}
                      </span>
                      <span className="book-perf-sub"> vs {pct(row.performance.benchmarkReturnPct)} bench</span>
                    </>
                  ) : <span className="book-perf-sub">No data yet</span>}
                </span>
                <span><RiskBadge risk={row.risk} /></span>
                <span>{row.lastReport ? row.lastReport.title : <span className="book-perf-sub">No reports yet</span>}</span>
                <span className="book-row-chevron">{expandedId === row.client.id ? '▾' : '▸'}</span>
              </div>
              {expandedId === row.client.id && (
                <div className="book-detail">
                  {/* The banner text is the backend's computed reason verbatim,
                      never generic copy -- see risk_status.py. */}
                  {row.risk && row.risk.status !== 'on_track' && (
                    <div className="alert-banner"><span>⚠ {row.risk.reason}</span></div>
                  )}

                  <div className="book-detail-actions">
                    <Link className="btn-link" to={`/internal-portal/clients/${row.client.id}`}>
                      Open full client profile →
                    </Link>
                    <button
                      type="button"
                      onClick={(event) => {
                        event.stopPropagation();
                        askLumina(
                          `Give me a briefing on ${row.client.name} — recent performance, where their reporting stands, and anything I should raise with them.`,
                          { clientId: row.client.id },
                        );
                      }}
                    >
                      Ask Lumina AI about this account
                    </button>
                  </div>

                  {detailLoading && <p className="field-hint">Loading…</p>}
                  {detail && (
                    <div className="book-detail-grid">
                      <div>
                        <h4>Top holdings</h4>
                        {detail.holdings.length === 0 && <p className="field-hint">No holdings on file.</p>}
                        <ul className="book-holdings-list">
                          {detail.holdings.map((holding) => (
                            <li key={holding.id}>
                              <span>{holding.security_name || holding.security_id}</span>
                              <span>{holding.weight_pct !== null ? `${holding.weight_pct.toFixed(1)}%` : '—'}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                      <div>
                        <h4>Performance by period</h4>
                        {detail.performance.length === 0 && <p className="field-hint">No performance snapshots on file.</p>}
                        <ul className="book-holdings-list">
                          {detail.performance.map((snapshot) => (
                            <li key={snapshot.id}>
                              <span>{snapshot.period_type}</span>
                              <span>{pct(snapshot.return_pct)} / {pct(snapshot.benchmark_return_pct)} bench</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                      <div>
                        <h4>Recent reports</h4>
                        {detail.reports.length === 0 && <p className="field-hint">No reports yet.</p>}
                        <ul className="book-holdings-list">
                          {detail.reports.map((report) => (
                            <li key={report.id}>
                              <Link to={`/reports/${report.id}`}>{report.title}</Link>
                              <StatusBadge status={report.status} />
                            </li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </React.Fragment>
          ))}

          {book && book.clients.length === 0 && (
            <p className="field-hint">
              {book.scope === 'mine'
                ? 'No clients are assigned to you yet. An admin sets a relationship manager on the Clients & Contacts page.'
                : 'No clients yet.'}
            </p>
          )}
          {book && book.clients.length > 0 && visibleClients.length === 0 && (
            <p className="field-hint">No client matches “{search}”.</p>
          )}
        </div>
      </section>
    </div>
  );
};

export default InternalPortal;
