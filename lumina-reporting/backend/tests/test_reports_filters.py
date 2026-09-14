from database import db_session
from models import Client, FundData

def _create_fund(app, name, asset_class):
    with app.app_context():
        fund = FundData(name=name, asset_class=asset_class)
        db_session.add(fund)
        db_session.commit()
        return fund.id

def _create_report(client, headers, sample_client, **overrides):
    payload = {'title': 'Untitled Report', 'client_id': sample_client}
    payload.update(overrides)
    response = client.post('/api/reports', headers=headers, json=payload)
    assert response.status_code == 201
    return response.get_json()

def test_create_report_persists_team_and_type(client, auth_headers, sample_client):
    report = _create_report(client, auth_headers, sample_client, title='Q3 Factsheet', team='Wealth Management', report_type='factsheet')
    assert report['team'] == 'Wealth Management'
    assert report['report_type'] == 'factsheet'

def test_filter_by_team(client, auth_headers, sample_client):
    _create_report(client, auth_headers, sample_client, title='A', team='Institutional Sales')
    _create_report(client, auth_headers, sample_client, title='B', team='Wealth Management')

    response = client.get('/api/reports?team=Wealth+Management', headers=auth_headers)
    titles = [r['title'] for r in response.get_json()]
    assert titles == ['B']

def test_filter_by_report_type(client, auth_headers, sample_client):
    _create_report(client, auth_headers, sample_client, title='Factsheet Report', report_type='factsheet')
    _create_report(client, auth_headers, sample_client, title='Pitchbook Report', report_type='pitchbook')

    response = client.get('/api/reports?report_type=pitchbook', headers=auth_headers)
    titles = [r['title'] for r in response.get_json()]
    assert titles == ['Pitchbook Report']

def test_filter_by_client_id(client, auth_headers, app):
    with app.app_context():
        other = Client(name='Other Institutional')
        db_session.add(other)
        db_session.commit()
        other_id = other.id

    first = _create_report(client, auth_headers, other_id, title='Other client report')
    response = client.get(f'/api/reports?client_id={other_id}', headers=auth_headers)
    ids = [r['id'] for r in response.get_json()]
    assert ids == [first['id']]

def test_filter_by_asset_class(client, auth_headers, sample_client, app):
    equity_fund = _create_fund(app, 'Global Equity Fund', 'Equity')
    bond_fund = _create_fund(app, 'Core Bond Fund', 'Fixed Income')

    _create_report(client, auth_headers, sample_client, title='Equity Report', fund_id=equity_fund)
    _create_report(client, auth_headers, sample_client, title='Bond Report', fund_id=bond_fund)

    response = client.get('/api/reports?asset_class=Fixed+Income', headers=auth_headers)
    titles = [r['title'] for r in response.get_json()]
    assert titles == ['Bond Report']

def test_filter_by_search_text(client, auth_headers, sample_client):
    _create_report(client, auth_headers, sample_client, title='Quarterly Holdings Report')
    _create_report(client, auth_headers, sample_client, title='Annual Performance Summary')

    response = client.get('/api/reports?q=holdings', headers=auth_headers)
    titles = [r['title'] for r in response.get_json()]
    assert titles == ['Quarterly Holdings Report']

def test_filters_compose(client, auth_headers, sample_client):
    _create_report(client, auth_headers, sample_client, title='Match', team='Ops', report_type='holdings')
    _create_report(client, auth_headers, sample_client, title='NoMatch1', team='Ops', report_type='factsheet')
    _create_report(client, auth_headers, sample_client, title='NoMatch2', team='Sales', report_type='holdings')

    response = client.get('/api/reports?team=Ops&report_type=holdings', headers=auth_headers)
    titles = [r['title'] for r in response.get_json()]
    assert titles == ['Match']

def test_client_role_filters_are_ignored(client, client_portal_headers, auth_headers, sample_client):
    report = _create_report(client, auth_headers, sample_client, title='Distributed report')
    client.post(f"/api/reports/{report['id']}/submit", headers=auth_headers)
    client.post(f"/api/reports/{report['id']}/approve", headers=auth_headers)
    client.post(f"/api/reports/{report['id']}/distribute", headers=auth_headers)

    response = client.get('/api/reports?team=Nonexistent-Team', headers=client_portal_headers)
    assert response.status_code == 200
    titles = [r['title'] for r in response.get_json()]
    assert titles == ['Distributed report']

def test_facets_returns_teams_types_and_asset_classes(client, auth_headers, sample_client, app):
    _create_fund(app, 'Global Equity Fund', 'Equity')
    _create_report(client, auth_headers, sample_client, title='A', team='Wealth Management', report_type='factsheet')

    response = client.get('/api/reports/facets', headers=auth_headers)
    assert response.status_code == 200
    body = response.get_json()
    assert body['teams'] == ['Wealth Management']
    assert 'factsheet' in body['reportTypes']
    assert body['assetClasses'] == ['Equity']

def test_facets_requires_auth(client):
    assert client.get('/api/reports/facets').status_code == 401
