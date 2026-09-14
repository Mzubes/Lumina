import React, { useEffect, useState } from 'react';
import { apiBaseUrl, apiFetch, isDemoMode } from '../api';

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
      <div className="page-heading">
        <div><span className="eyebrow">Client experience</span><h1>Client Portal</h1></div>
        {isDemoMode && <span className="demo-badge">Demo data</span>}
      </div>

      {hasPortfolio && (
        <>
          {portfolio.performance.length > 0 && (
            <section className="panel">
              <div className="panel-header"><h2>Performance</h2></div>
              {portfolio.asOfDate && <p className="panel-subtitle">As of {portfolio.asOfDate}</p>}
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
      )}

      <section className="panel"><h2>Your reports</h2><ul className="report-list">
        {reports.map(report => (
          <li key={report.id}>
            {report.title}
            {report.file_path
              ? <a href={`${apiBaseUrl}${report.file_path}`} target="_blank" rel="noreferrer"><button>View</button></a>
              : <button disabled>View</button>}
          </li>
        ))}
        {reports.length === 0 && <li>No reports have been distributed to you yet.</li>}
      </ul></section>
    </div>
  );
};

export default ClientPortal;
