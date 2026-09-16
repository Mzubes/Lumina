import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { apiBaseUrl, apiFetch, isDemoMode } from '../api';
import CompositionBar from '../components/charts/CompositionBar';

const demoReports = [
  { id: 1, title: 'Q2 Institutional Portfolio Report', file_path: null, created_at: null },
  { id: 2, title: 'July Performance Summary', file_path: null, created_at: null },
];

const demoPortfolio = {
  asOfDate: '2026-06-30',
  holdings: [
    { id: 1, security_name: 'Apple Inc.', asset_class: 'Equity', market_value: 175000, weight_pct: 18.2 },
    { id: 2, security_name: 'US Treasury 10Y', asset_class: 'Fixed Income', market_value: 120000, weight_pct: 12.5 },
    { id: 3, security_name: 'Microsoft Corp.', asset_class: 'Equity', market_value: 96500, weight_pct: 10.1 },
  ],
  performance: [
    { period_type: 'QTD', return_pct: 3.2, benchmark_return_pct: 2.8 },
    { period_type: 'YTD', return_pct: 8.1, benchmark_return_pct: 7.4 },
    { period_type: '1Y', return_pct: 14.6, benchmark_return_pct: 15.2 },
  ],
};

const formatCurrency = (value) => (
  value == null ? '—' : `$${Number(value).toLocaleString(undefined, { maximumFractionDigits: 0 })}`
);
const formatPercent = (value) => (value == null ? '—' : `${value > 0 ? '+' : ''}${Number(value).toFixed(1)}%`);

const CATEGORICAL_COLORS = ['var(--cat-1)', 'var(--cat-2)', 'var(--cat-3)', 'var(--cat-4)', 'var(--cat-5)', 'var(--cat-6)'];

// Composition rides on the stacked/segmented bar, not a donut (dataviz skill:
// part-to-whole -> stacked bar; donut stays deprioritized). Folds past the
// 6-slot categorical ceiling into "Other", matching the same pattern the
// dashboard aggregates already use server-side.
const assetAllocation = (holdings) => {
  const totals = {};
  holdings.forEach((holding) => {
    const label = holding.asset_class || 'Unassigned';
    totals[label] = (totals[label] || 0) + (Number(holding.market_value) || 0);
  });
  const sorted = Object.entries(totals).sort((a, b) => b[1] - a[1]);
  const top = sorted.slice(0, 6).map(([label, value], index) => ({
    label, value, color: label === 'Unassigned' ? 'var(--cat-other)' : CATEGORICAL_COLORS[index % CATEGORICAL_COLORS.length],
  }));
  const overflow = sorted.slice(6).reduce((sum, [, value]) => sum + value, 0);
  if (overflow) top.push({ label: 'Other', value: overflow, color: 'var(--cat-other)' });
  return top;
};

const ClientPortal = () => {
  const [reports, setReports] = useState([]);
  const [portfolio, setPortfolio] = useState(null);

  useEffect(() => {
    if (isDemoMode) { setReports(demoReports); setPortfolio(demoPortfolio); return; }
    apiFetch('/api/reports').then(setReports).catch(() => setReports(demoReports));
    apiFetch('/api/portfolio').then(setPortfolio).catch(() => setPortfolio(null));
  }, []);

  const hasPortfolio = portfolio && (portfolio.holdings.length > 0 || portfolio.performance.length > 0);

  return (
    <div className="client-portal">
      <div className="client-portal-hero">
        <div className="client-portal-hero-text">
          <span className="eyebrow">Client experience</span>
          <h1>Welcome back.</h1>
          <p className="client-portal-hero-sub">
            Your portfolio and the reports your advisor has shared with you, in one place.
          </p>
        </div>
        <div className="client-portal-hero-chips">
          {portfolio && portfolio.asOfDate && <span className="client-portal-asof-chip">As of {portfolio.asOfDate}</span>}
          {isDemoMode && <span className="demo-badge">Demo data</span>}
        </div>
      </div>

      {hasPortfolio ? (
        <>
          {portfolio.performance.length > 0 && (
            <section className="panel">
              <div className="panel-header"><h2>Performance</h2></div>
              <div className="metric-grid">
                {portfolio.performance.map(row => {
                  const hasBenchmark = row.benchmark_return_pct != null;
                  const delta = hasBenchmark ? row.return_pct - row.benchmark_return_pct : null;
                  return (
                    <article className="metric-card" key={row.period_type}>
                      <span>{row.period_type}</span>
                      <strong>{formatPercent(row.return_pct)}</strong>
                      {hasBenchmark && (
                        <span className={`metric-card-delta ${delta >= 0 ? 'up' : 'down'}`}>
                          {delta >= 0 ? '▲' : '▼'} {Math.abs(delta).toFixed(1)}% vs benchmark
                        </span>
                      )}
                    </article>
                  );
                })}
              </div>
            </section>
          )}

          {portfolio.holdings.length > 0 && (
            <section className="panel">
              <div className="panel-header"><h2>Asset allocation</h2></div>
              <CompositionBar title="Asset allocation" unitLabel="in assets" data={assetAllocation(portfolio.holdings)} />
            </section>
          )}

          {portfolio.holdings.length > 0 && (
            <section className="panel">
              <h2>Holdings</h2>
              <table className="data-table">
                <thead>
                  <tr><th>Security</th><th>Asset class</th><th className="num">Market value</th><th className="num">Weight</th></tr>
                </thead>
                <tbody>
                  {portfolio.holdings.map(holding => (
                    <tr key={holding.id}>
                      <td>{holding.security_name || holding.security_id}</td>
                      <td>{holding.asset_class || '—'}</td>
                      <td className="num">{formatCurrency(holding.market_value)}</td>
                      <td className="num">{holding.weight_pct != null ? `${holding.weight_pct}%` : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}
        </>
      ) : (
        <section className="panel client-portal-empty">
          <h2>Your portfolio is on its way</h2>
          <p>
            Your holdings and performance will appear here once your advisor connects your
            account. Any reports already shared with you are listed below.
          </p>
        </section>
      )}

      <section className="panel"><h2>Your reports</h2><ul className="report-list">
        {reports.map(report => (
          <li key={report.id}>
            <Link to={`/reports/${report.id}`} className="reports-table-title-link">{report.title}</Link>
            {report.file_path
              ? <a href={`${apiBaseUrl}${report.file_path}`} target="_blank" rel="noreferrer"><button>View PDF</button></a>
              : <button disabled>View PDF</button>}
          </li>
        ))}
        {reports.length === 0 && <li className="client-portal-reports-empty">No reports have been distributed to you yet.</li>}
      </ul></section>
    </div>
  );
};

export default ClientPortal;
