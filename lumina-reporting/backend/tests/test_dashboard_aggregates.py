import json

from database import db_session
from models import DataSource, FundData

def _create_report(client, headers, sample_client, **overrides):
    payload = {'title': 'Untitled Report', 'client_id': sample_client}
    payload.update(overrides)
    response = client.post('/api/reports', headers=headers, json=payload)
    assert response.status_code == 201
    return response.get_json()

def test_reports_by_team_folds_past_top_six(client, auth_headers, sample_client):
    # 8 distinct teams, one report each -> top 6 by count kept, remaining 2 folded into "Other".
    for index in range(8):
        _create_report(client, auth_headers, sample_client, title=f'Report {index}', team=f'Team {index}')

    body = client.get('/api/dashboard', headers=auth_headers).get_json()
    by_team = body['reportsByTeam']
    other_bucket = next((row for row in by_team if row['label'] == 'Other'), None)

    assert len(by_team) == 7  # 6 named + Other
    assert other_bucket['count'] == 2

def test_reports_by_asset_class_via_fund(client, auth_headers, sample_client, app):
    with app.app_context():
        fund = FundData(name='Global Equity Fund', asset_class='Equity')
        db_session.add(fund)
        db_session.commit()
        fund_id = fund.id

    _create_report(client, auth_headers, sample_client, title='Equity Report', fund_id=fund_id)
    _create_report(client, auth_headers, sample_client, title='No Fund Report')

    body = client.get('/api/dashboard', headers=auth_headers).get_json()
    labels = {row['label']: row['count'] for row in body['reportsByAssetClass']}
    assert labels['Equity'] == 1
    assert labels['Unassigned'] == 1

def test_failed_data_sources_surfaced(client, auth_headers, app):
    with app.app_context():
        source = DataSource(
            name='Broken Warehouse', type='snowflake', config=json.dumps({}),
            last_sync_status='error', last_sync_message='Connection timed out', created_by=1,
        )
        db_session.add(source)
        db_session.commit()
        source_id = source.id

    body = client.get('/api/dashboard', headers=auth_headers).get_json()
    assert body['failedDataSources'] == [
        {'id': source_id, 'name': 'Broken Warehouse', 'message': 'Connection timed out'},
    ]
