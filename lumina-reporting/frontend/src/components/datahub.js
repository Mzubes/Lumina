import React, { useState, useEffect } from 'react';

const DataHub = () => {
  const [funds, setFunds] = useState([]);

  useEffect(() => {
    fetch('/api/funds')
      .then(res => res.json())
      .then(data => setFunds(data));
  }, []);

  return (
    <div className="data-hub">
      <h1>Data Hub</h1>
      <ul>
        {funds.map(fund => (
          <li key={fund.id}>{fund.name} - {fund.asset_class}</li>
        ))}
      </ul>
    </div>
  );
};

export default DataHub;
