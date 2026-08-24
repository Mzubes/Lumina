import React, { useState, useEffect } from 'react';
import { apiFetch, isDemoMode } from '../api';

const demoFunds = [
  { id: 1, name: 'Global Equity Strategy', asset_class: 'Public Equity' },
  { id: 2, name: 'Core Fixed Income', asset_class: 'Fixed Income' },
  { id: 3, name: 'Multi-Asset Opportunities', asset_class: 'Multi-Asset' },
];

const DataHub = () => {
  const [funds, setFunds] = useState([]);

  useEffect(() => {
    if (isDemoMode) { setFunds(demoFunds); return; }
    apiFetch('/api/funds').then(setFunds).catch(() => setFunds(demoFunds));
  }, []);

  return (
    <div className="data-hub">
      <span className="eyebrow">Connected data</span><h1>Data Hub</h1>
      <div className="panel"><ul className="report-list">
        {funds.map(fund => (
          <li key={fund.id}>{fund.name} - {fund.asset_class}</li>
        ))}
      </ul></div>
    </div>
  );
};

export default DataHub;
