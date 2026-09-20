import datetime

import requests

from connectors.errors import ConnectorError
from connectors.land import map_rows, replace_holdings, replace_performance

def _auth_headers(config):
    token = config.get('auth_token')
    if not token:
        return {}
    if config.get('auth_type') == 'api_key':
        return {'X-Api-Key': token}
    return {'Authorization': f'Bearer {token}'}

def _fetch(base_url, path, headers, client_id):
    if not path:
        return []
    url = base_url.rstrip('/') + path
    try:
        response = requests.get(url, headers=headers, params={'client_id': client_id}, timeout=15)
        response.raise_for_status()
    except requests.RequestException as error:
        raise ConnectorError(f"API request to {url} failed: {error}") from error
    try:
        data = response.json()
    except ValueError as error:
        raise ConnectorError(f"API response from {url} was not valid JSON: {error}") from error
    if not isinstance(data, list):
        raise ConnectorError(f"Expected a JSON array of records from {url}")
    return data

def sync(data_source, client_id, fund_id=None, as_of_date=None):
    as_of_date = as_of_date or datetime.date.today()
    config = data_source.config_dict()

    base_url = config.get('base_url')
    if not base_url:
        raise ConnectorError("base_url is required")
    headers = _auth_headers(config)
    column_map = config.get('column_map') or []

    raw_holdings = _fetch(base_url, config.get('holdings_path'), headers, client_id)
    raw_performance = _fetch(base_url, config.get('performance_path'), headers, client_id)

    holdings = replace_holdings(
        map_rows(raw_holdings, column_map), client_id, fund_id, as_of_date, data_source.id,
    )
    performance = replace_performance(
        map_rows(raw_performance, column_map), client_id, fund_id, as_of_date, data_source.id,
    )

    return {'holdings_count': len(holdings), 'performance_count': len(performance)}
