from unittest.mock import MagicMock, patch

SNOWFLAKE_CONFIG = {
    'account': 'acme', 'user': 'svc', 'password': 'super-secret', 'warehouse': 'WH',
    'database': 'DB', 'schema': 'PUBLIC', 'role': 'READER',
    'holdings_table': 'holdings_view', 'performance_table': 'performance_view',
    'client_column': 'client_ref', 'column_map': [],
}

def test_create_data_source_requires_admin(client, editor_headers):
    response = client.post('/api/data-sources', headers=editor_headers, json={
        'name': 'Warehouse', 'type': 'snowflake', 'config': SNOWFLAKE_CONFIG,
    })
    assert response.status_code == 403

def test_create_data_source_redacts_secret(client, auth_headers):
    response = client.post('/api/data-sources', headers=auth_headers, json={
        'name': 'Warehouse', 'type': 'snowflake', 'config': SNOWFLAKE_CONFIG,
    })
    assert response.status_code == 201
    body = response.get_json()
    assert 'password' not in body['config']
    assert body['config']['holdings_table'] == 'holdings_view'

def test_create_data_source_rejects_bad_identifier(client, auth_headers):
    bad_config = dict(SNOWFLAKE_CONFIG, holdings_table='holdings; DROP TABLE users')
    response = client.post('/api/data-sources', headers=auth_headers, json={
        'name': 'Warehouse', 'type': 'snowflake', 'config': bad_config,
    })
    assert response.status_code == 400

def test_list_and_get_redact_secrets(client, auth_headers):
    created = client.post('/api/data-sources', headers=auth_headers, json={
        'name': 'Warehouse', 'type': 'snowflake', 'config': SNOWFLAKE_CONFIG,
    }).get_json()

    listed = client.get('/api/data-sources', headers=auth_headers)
    assert listed.status_code == 200
    assert 'password' not in listed.get_json()[0]['config']

    fetched = client.get(f"/api/data-sources/{created['id']}", headers=auth_headers)
    assert fetched.status_code == 200
    assert 'password' not in fetched.get_json()['config']

def test_get_missing_data_source_404(client, auth_headers):
    assert client.get('/api/data-sources/999', headers=auth_headers).status_code == 404

def test_update_preserves_password_when_omitted(client, auth_headers):
    created = client.post('/api/data-sources', headers=auth_headers, json={
        'name': 'Warehouse', 'type': 'snowflake', 'config': SNOWFLAKE_CONFIG,
    }).get_json()
    source_id = created['id']

    # Simulate the edit form re-submitting what GET returned (no password key).
    edited_config = dict(created['config'], holdings_table='new_holdings_view')
    updated = client.put(f'/api/data-sources/{source_id}', headers=auth_headers, json={
        'name': 'Warehouse', 'type': 'snowflake', 'config': edited_config,
    })
    assert updated.status_code == 200
    assert updated.get_json()['config']['holdings_table'] == 'new_holdings_view'

    from database import db_session
    from models import DataSource
    stored = db_session.query(DataSource).filter_by(id=source_id).first()
    assert stored.config_dict()['password'] == 'super-secret'

def test_sync_requires_client_id(client, auth_headers):
    created = client.post('/api/data-sources', headers=auth_headers, json={
        'name': 'Warehouse', 'type': 'snowflake', 'config': SNOWFLAKE_CONFIG,
    }).get_json()
    response = client.post(f"/api/data-sources/{created['id']}/sync", headers=auth_headers, json={})
    assert response.status_code == 400

def test_sync_success_updates_status(client, auth_headers, sample_client):
    created = client.post('/api/data-sources', headers=auth_headers, json={
        'name': 'Warehouse', 'type': 'snowflake', 'config': SNOWFLAKE_CONFIG,
    }).get_json()

    fake_cursor = MagicMock()
    fake_cursor.fetchall.side_effect = [[], []]
    fake_connection = MagicMock()
    fake_connection.cursor.return_value = fake_cursor

    with patch('connectors.snowflake_connector.snowflake.connector.connect', return_value=fake_connection):
        response = client.post(f"/api/data-sources/{created['id']}/sync", headers=auth_headers, json={
            'client_id': sample_client,
        })
    assert response.status_code == 200
    body = response.get_json()
    assert body['last_sync_status'] == 'success'
    assert body['last_synced_at'] is not None

def test_sync_failure_records_error_status(client, auth_headers, sample_client):
    created = client.post('/api/data-sources', headers=auth_headers, json={
        'name': 'Warehouse', 'type': 'snowflake', 'config': SNOWFLAKE_CONFIG,
    }).get_json()

    with patch('connectors.snowflake_connector.snowflake.connector.connect', side_effect=RuntimeError('unreachable')):
        response = client.post(f"/api/data-sources/{created['id']}/sync", headers=auth_headers, json={
            'client_id': sample_client,
        })
    assert response.status_code == 502

    followup = client.get(f"/api/data-sources/{created['id']}", headers=auth_headers)
    assert followup.get_json()['last_sync_status'] == 'error'
