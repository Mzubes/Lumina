import React, { useEffect, useState } from 'react';
import { apiFetch, isDemoMode } from '../api';

const TARGET_FIELDS = [
  { value: 'security_id', label: 'Security ID' },
  { value: 'security_name', label: 'Security Name' },
  { value: 'asset_class', label: 'Asset Class' },
  { value: 'quantity', label: 'Quantity' },
  { value: 'market_value', label: 'Market Value' },
  { value: 'currency', label: 'Currency' },
  { value: 'weight_pct', label: 'Weight %' },
  { value: 'period_type', label: 'Performance Period (e.g. QTD)' },
  { value: 'return_pct', label: 'Return %' },
  { value: 'benchmark_return_pct', label: 'Benchmark Return %' },
];

const emptyColumnRow = () => ({ source_column: '', target_field: TARGET_FIELDS[0].value });

const initialSnowflakeFields = {
  account: '', user: '', password: '', warehouse: '', database: '', schema: '', role: '',
  holdings_table: '', performance_table: '', client_column: '',
};

const initialApiFields = {
  base_url: '', auth_type: 'bearer', auth_token: '', holdings_path: '', performance_path: '',
};

const SYNC_STATUS_CLASS = { success: 'distributed', error: 'review' };

const DataSources = () => {
  const [sources, setSources] = useState([]);
  const [clients, setClients] = useState([]);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');

  const [name, setName] = useState('');
  const [type, setType] = useState('snowflake');
  const [snowflakeFields, setSnowflakeFields] = useState(initialSnowflakeFields);
  const [apiFields, setApiFields] = useState(initialApiFields);
  const [columnMap, setColumnMap] = useState([emptyColumnRow()]);

  const [syncSourceId, setSyncSourceId] = useState(null);
  const [syncClientId, setSyncClientId] = useState('');

  const loadSources = () => {
    if (isDemoMode) return;
    apiFetch('/api/data-sources').then(setSources).catch(requestError => setError(requestError.message));
  };

  useEffect(() => {
    if (isDemoMode) return;
    loadSources();
    apiFetch('/api/clients').then(setClients).catch(() => {});
  }, []);

  const updateColumnRow = (index, field, value) => {
    setColumnMap(rows => rows.map((row, i) => (i === index ? { ...row, [field]: value } : row)));
  };
  const addColumnRow = () => setColumnMap(rows => [...rows, emptyColumnRow()]);
  const removeColumnRow = (index) => setColumnMap(rows => rows.filter((_, i) => i !== index));

  const resetForm = () => {
    setName('');
    setSnowflakeFields(initialSnowflakeFields);
    setApiFields(initialApiFields);
    setColumnMap([emptyColumnRow()]);
  };

  const handleCreate = async (event) => {
    event.preventDefault();
    setError('');
    const config = {
      ...(type === 'snowflake' ? snowflakeFields : apiFields),
      column_map: columnMap.filter(row => row.source_column),
    };
    try {
      await apiFetch('/api/data-sources', { method: 'POST', body: JSON.stringify({ name, type, config }) });
      resetForm();
      loadSources();
    } catch (requestError) { setError(requestError.message); }
  };

  const handleSync = async (event) => {
    event.preventDefault();
    setError('');
    setStatus('');
    if (!syncClientId) { setError('Choose a client to sync data for.'); return; }
    try {
      const result = await apiFetch(`/api/data-sources/${syncSourceId}/sync`, {
        method: 'POST', body: JSON.stringify({ client_id: Number(syncClientId) }),
      });
      setStatus(result.last_sync_message || 'Sync complete.');
      loadSources();
    } catch (requestError) { setError(requestError.message); }
  };

  return (
    <div className="data-sources">
      <div className="page-heading">
        <div><span className="eyebrow">Connected data</span><h1>Data Sources</h1></div>
        {isDemoMode && <span className="demo-badge">Demo data</span>}
      </div>

      <section className="panel">
        <h2>Connections</h2>
        <ul className="report-list">
          {sources.map(source => (
            <li key={source.id}>
              <span>{source.name} <em className="muted">({source.type})</em></span>
              <span className={`status-badge status-${SYNC_STATUS_CLASS[source.last_sync_status] || 'draft'}`}>
                {source.last_sync_status || 'never synced'}
              </span>
              <button type="button" onClick={() => { setSyncSourceId(source.id); setSyncClientId(''); setStatus(''); }}>
                Sync now
              </button>
            </li>
          ))}
          {sources.length === 0 && <li>No data sources connected yet.</li>}
        </ul>
      </section>

      {syncSourceId && (
        <section className="panel">
          <h2>Sync data source</h2>
          <form onSubmit={handleSync}>
            <label>Client
              <select value={syncClientId} onChange={e => setSyncClientId(e.target.value)} required>
                <option value="">Choose a client…</option>
                {clients.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </label>
            <div className="form-actions">
              <button type="submit">Sync now</button>
              <button type="button" onClick={() => setSyncSourceId(null)}>Cancel</button>
            </div>
          </form>
          {status && <p className="form-message form-message-success">{status}</p>}
        </section>
      )}

      <section className="panel">
        <h2>Connect a new data source</h2>
        <form onSubmit={handleCreate}>
          <label>Name
            <input value={name} onChange={e => setName(e.target.value)} required />
          </label>
          <label>Type
            <select value={type} onChange={e => setType(e.target.value)}>
              <option value="snowflake">Snowflake</option>
              <option value="api">API</option>
            </select>
          </label>

          {type === 'snowflake' ? (
            <>
              <label>Account
                <input value={snowflakeFields.account} onChange={e => setSnowflakeFields({ ...snowflakeFields, account: e.target.value })} required />
              </label>
              <label>Username
                <input value={snowflakeFields.user} onChange={e => setSnowflakeFields({ ...snowflakeFields, user: e.target.value })} required />
              </label>
              <label>Password
                <input type="password" value={snowflakeFields.password} onChange={e => setSnowflakeFields({ ...snowflakeFields, password: e.target.value })} required />
              </label>
              <label>Warehouse
                <input value={snowflakeFields.warehouse} onChange={e => setSnowflakeFields({ ...snowflakeFields, warehouse: e.target.value })} required />
              </label>
              <label>Database
                <input value={snowflakeFields.database} onChange={e => setSnowflakeFields({ ...snowflakeFields, database: e.target.value })} required />
              </label>
              <label>Schema
                <input value={snowflakeFields.schema} onChange={e => setSnowflakeFields({ ...snowflakeFields, schema: e.target.value })} required />
              </label>
              <label>Role
                <input value={snowflakeFields.role} onChange={e => setSnowflakeFields({ ...snowflakeFields, role: e.target.value })} />
              </label>
              <label>Holdings table
                <input
                  value={snowflakeFields.holdings_table}
                  onChange={e => setSnowflakeFields({ ...snowflakeFields, holdings_table: e.target.value })}
                  placeholder="e.g. holdings_view" required
                />
              </label>
              <label>Performance table
                <input
                  value={snowflakeFields.performance_table}
                  onChange={e => setSnowflakeFields({ ...snowflakeFields, performance_table: e.target.value })}
                  placeholder="e.g. performance_view" required
                />
              </label>
              <label>Client column
                <input
                  value={snowflakeFields.client_column}
                  onChange={e => setSnowflakeFields({ ...snowflakeFields, client_column: e.target.value })}
                  placeholder="the column that identifies which client each row belongs to" required
                />
              </label>
            </>
          ) : (
            <>
              <label>Base URL
                <input value={apiFields.base_url} onChange={e => setApiFields({ ...apiFields, base_url: e.target.value })} placeholder="https://data.example.com" required />
              </label>
              <label>Auth type
                <select value={apiFields.auth_type} onChange={e => setApiFields({ ...apiFields, auth_type: e.target.value })}>
                  <option value="bearer">Bearer token</option>
                  <option value="api_key">API key</option>
                </select>
              </label>
              <label>Token
                <input type="password" value={apiFields.auth_token} onChange={e => setApiFields({ ...apiFields, auth_token: e.target.value })} required />
              </label>
              <label>Holdings path
                <input value={apiFields.holdings_path} onChange={e => setApiFields({ ...apiFields, holdings_path: e.target.value })} placeholder="/v1/holdings" />
              </label>
              <label>Performance path
                <input value={apiFields.performance_path} onChange={e => setApiFields({ ...apiFields, performance_path: e.target.value })} placeholder="/v1/performance" />
              </label>
            </>
          )}

          <h3>Map your columns</h3>
          <p className="field-hint">Tell us which column in your data holds each value.</p>
          {columnMap.map((row, index) => (
            <div className="column-map-row" key={index}>
              <input
                placeholder="Your column name"
                value={row.source_column}
                onChange={e => updateColumnRow(index, 'source_column', e.target.value)}
              />
              <select value={row.target_field} onChange={e => updateColumnRow(index, 'target_field', e.target.value)}>
                {TARGET_FIELDS.map(field => <option key={field.value} value={field.value}>{field.label}</option>)}
              </select>
              <button type="button" onClick={() => removeColumnRow(index)}>Remove</button>
            </div>
          ))}
          <button type="button" onClick={addColumnRow}>Add column mapping</button>

          <div className="form-actions">
            <button type="submit">Connect data source</button>
          </div>
        </form>
      </section>

      {error && <p className="form-message">{error}</p>}
    </div>
  );
};

export default DataSources;
