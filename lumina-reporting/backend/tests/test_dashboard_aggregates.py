import json

from database import db_session
from models import DataSource, FundData, WorkflowGroup

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

def test_reports_by_week_has_fixed_window_and_zero_fills(client, auth_headers):
    body = client.get('/api/dashboard', headers=auth_headers).get_json()
    assert len(body['reportsByWeek']) == 8
    assert all(row['count'] == 0 for row in body['reportsByWeek'])

def test_reports_by_week_counts_current_week(client, auth_headers, sample_client):
    _create_report(client, auth_headers, sample_client, title='Report A')
    _create_report(client, auth_headers, sample_client, title='Report B')

    body = client.get('/api/dashboard', headers=auth_headers).get_json()
    # last bucket is always the current week -- both reports were just created.
    assert body['reportsByWeek'][-1]['count'] == 2
    assert sum(row['count'] for row in body['reportsByWeek']) == 2

def _compliance_group_id(app, compliance_headers):
    # compliance_headers (tests/conftest.py) creates the "Compliance"
    # WorkflowGroup as a side effect of seeding its editor+group-member user.
    with app.app_context():
        return db_session.query(WorkflowGroup).filter_by(name='Compliance').first().id

def _create_reviewable_report(client, editor_headers, auth_headers, sample_client, group_id):
    components = [{"id": "c1", "type": "text_block", "title": "Disclosures", "review_group_id": group_id,
                   "data_binding": {"static_text": "All investments involve risk."}}]
    template = client.post('/api/templates', headers=editor_headers, json={
        'name': 'Reviewable Template', 'components': components,
    }).get_json()
    return client.post('/api/reports', headers=auth_headers, json={
        'title': 'Reviewable Report', 'client_id': sample_client, 'template_id': template['id'],
    }).get_json()

def test_pending_component_reviews_only_counts_in_flight_reports(client, editor_headers, auth_headers, app, compliance_headers, sample_client):
    group_id = _compliance_group_id(app, compliance_headers)
    report = _create_reviewable_report(client, editor_headers, auth_headers, sample_client, group_id)

    # still draft -> not counted yet.
    draft_body = client.get('/api/dashboard', headers=auth_headers).get_json()
    assert draft_body['pendingComponentReviews'] == 0

    client.post(f"/api/reports/{report['id']}/submit", headers=auth_headers)
    review_body = client.get('/api/dashboard', headers=auth_headers).get_json()
    assert review_body['pendingComponentReviews'] == 1

def test_pending_component_reviews_excludes_already_reviewed(client, editor_headers, auth_headers, compliance_headers, app, sample_client):
    group_id = _compliance_group_id(app, compliance_headers)
    report = _create_reviewable_report(client, editor_headers, auth_headers, sample_client, group_id)
    client.post(f"/api/reports/{report['id']}/submit", headers=auth_headers)
    client.post(f"/api/reports/{report['id']}/components/c1/review", headers=compliance_headers)

    body = client.get('/api/dashboard', headers=auth_headers).get_json()
    assert body['pendingComponentReviews'] == 0
