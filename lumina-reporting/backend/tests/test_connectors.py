from unittest.mock import MagicMock, patch

import pytest
import requests

from connectors.api_connector import sync as api_sync
from connectors.errors import ConnectorError
from connectors.snowflake_connector import sync as snowflake_sync
from database import db_session
from models import DataSource, Holding, PerformanceSnapshot

SNOWFLAKE_CONFIG = {
    'account': 'acme', 'user': 'svc', 'password': 'secret', 'warehouse': 'WH',
    'database': 'DB', 'schema': 'PUBLIC', 'role': 'READER',
    'holdings_table': 'holdings_view', 'performance_table': 'performance_view',
    'client_column': 'client_ref',
    'column_map': [
        {'source_column': 'TICKER', 'target_field': 'security_id'},
        {'source_column': 'NAME', 'target_field': 'security_name'},
        {'source_column': 'VALUE', 'target_field': 'market_value'},
        {'source_column': 'PERIOD', 'target_field': 'period_type'},
        {'source_column': 'RETURN', 'target_field': 'return_pct'},
    ],
}

API_CONFIG = {
    'base_url': 'https://data.example.com', 'auth_type': 'bearer', 'auth_token': 'tok-123',
    'holdings_path': '/v1/holdings', 'performance_path': '/v1/performance',
    'column_map': SNOWFLAKE_CONFIG['column_map'],
}

def _make_data_source(app, config, source_type):
    import json
    with app.app_context():
        source = DataSource(name='Test Source', type=source_type, config=json.dumps(config), created_by=1)
        db_session.add(source)
        db_session.commit()
        return source.id

def _get_data_source(app, source_id):
    with app.app_context():
        return db_session.get(DataSource, source_id)

def test_snowflake_sync_lands_mapped_rows(app, sample_client):
    source_id = _make_data_source(app, SNOWFLAKE_CONFIG, 'snowflake')

    fake_cursor = MagicMock()
    fake_cursor.fetchall.side_effect = [
        [{'TICKER': 'AAPL', 'NAME': 'Apple Inc.', 'VALUE': 1000.50}],
        [{'PERIOD': 'QTD', 'RETURN': 2.5}],
    ]
    fake_connection = MagicMock()
    fake_connection.cursor.return_value = fake_cursor

    with app.app_context():
        source = db_session.get(DataSource, source_id)
        with patch('connectors.snowflake_connector.snowflake.connector.connect', return_value=fake_connection):
            result = snowflake_sync(source, client_id=sample_client)

        assert result == {'holdings_count': 1, 'performance_count': 1}
        holding = db_session.query(Holding).filter_by(client_id=sample_client).one()
        assert holding.security_id == 'AAPL'
        assert holding.security_name == 'Apple Inc.'
        assert float(holding.market_value) == 1000.50
        assert holding.source_id == source_id

        snapshot = db_session.query(PerformanceSnapshot).filter_by(client_id=sample_client).one()
        assert snapshot.period_type == 'QTD'
        assert float(snapshot.return_pct) == 2.5

def test_snowflake_sync_is_idempotent(app, sample_client):
    source_id = _make_data_source(app, SNOWFLAKE_CONFIG, 'snowflake')
    fake_cursor = MagicMock()
    fake_cursor.fetchall.side_effect = [
        [{'TICKER': 'AAPL', 'NAME': 'Apple Inc.', 'VALUE': 1000.50}],
        [{'PERIOD': 'QTD', 'RETURN': 2.5}],
    ] * 2
    fake_connection = MagicMock()
    fake_connection.cursor.return_value = fake_cursor

    with app.app_context():
        source = db_session.get(DataSource, source_id)
        with patch('connectors.snowflake_connector.snowflake.connector.connect', return_value=fake_connection):
            snowflake_sync(source, client_id=sample_client)
            snowflake_sync(source, client_id=sample_client)

        assert db_session.query(Holding).filter_by(client_id=sample_client).count() == 1
        assert db_session.query(PerformanceSnapshot).filter_by(client_id=sample_client).count() == 1

def test_snowflake_connect_error_wrapped(app, sample_client):
    source_id = _make_data_source(app, SNOWFLAKE_CONFIG, 'snowflake')
    with app.app_context():
        source = db_session.get(DataSource, source_id)
        with patch('connectors.snowflake_connector.snowflake.connector.connect', side_effect=RuntimeError('boom')):
            with pytest.raises(ConnectorError):
                snowflake_sync(source, client_id=sample_client)

def test_snowflake_invalid_identifier_rejected(app, sample_client):
    bad_config = dict(SNOWFLAKE_CONFIG, holdings_table='holdings; DROP TABLE users')
    source_id = _make_data_source(app, bad_config, 'snowflake')
    with app.app_context():
        source = db_session.get(DataSource, source_id)
        with patch('connectors.snowflake_connector.snowflake.connector.connect') as mock_connect:
            with pytest.raises(ConnectorError):
                snowflake_sync(source, client_id=sample_client)
            mock_connect.assert_not_called()

def test_api_sync_lands_mapped_rows(app, sample_client):
    source_id = _make_data_source(app, API_CONFIG, 'api')

    holdings_response = MagicMock()
    holdings_response.json.return_value = [{'TICKER': 'MSFT', 'NAME': 'Microsoft', 'VALUE': 500.0}]
    performance_response = MagicMock()
    performance_response.json.return_value = [{'PERIOD': 'YTD', 'RETURN': 4.1}]

    with app.app_context():
        source = db_session.get(DataSource, source_id)
        with patch('connectors.api_connector.requests.get', side_effect=[holdings_response, performance_response]):
            result = api_sync(source, client_id=sample_client)

        assert result == {'holdings_count': 1, 'performance_count': 1}
        holding = db_session.query(Holding).filter_by(client_id=sample_client).one()
        assert holding.security_id == 'MSFT'

def test_api_sync_http_error_wrapped(app, sample_client):
    source_id = _make_data_source(app, API_CONFIG, 'api')
    with app.app_context():
        source = db_session.get(DataSource, source_id)
        with patch('connectors.api_connector.requests.get', side_effect=requests.ConnectionError('down')):
            with pytest.raises(ConnectorError):
                api_sync(source, client_id=sample_client)

def test_api_sync_non_list_response_rejected(app, sample_client):
    source_id = _make_data_source(app, API_CONFIG, 'api')
    bad_response = MagicMock()
    bad_response.json.return_value = {'not': 'a list'}
    with app.app_context():
        source = db_session.get(DataSource, source_id)
        with patch('connectors.api_connector.requests.get', return_value=bad_response):
            with pytest.raises(ConnectorError):
                api_sync(source, client_id=sample_client)
