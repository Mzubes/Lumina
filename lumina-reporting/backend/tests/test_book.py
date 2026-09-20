import datetime

from database import db_session
from models import Holding, PerformanceSnapshot

def test_book_totals_across_clients(client, auth_headers, sample_client, sample_holding, sample_performance):
    response = client.get('/api/book', headers=auth_headers)
    assert response.status_code == 200
    body = response.get_json()
    assert body['clientCount'] == 1
    assert body['totalAum'] == 17500.00
    row = body['clients'][0]
    assert row['client']['id'] == sample_client
    assert row['aum'] == 17500.00
    assert row['performance']['periodType'] == 'QTD'

def test_book_flags_underperformance(client, auth_headers, app, sample_client):
    with app.app_context():
        db_session.add(PerformanceSnapshot(
            client_id=sample_client, as_of_date=datetime.date(2026, 6, 30),
            period_type='YTD', return_pct=4.0, benchmark_return_pct=6.0,
        ))
        db_session.commit()
    body = client.get('/api/book', headers=auth_headers).get_json()
    assert body['underperformingCount'] == 1
    assert body['clients'][0]['performance']['isUnderperforming'] is True

def test_book_with_no_data_yet(client, auth_headers, sample_client):
    # A brand-new client with no holdings/performance/reports shouldn't
    # crash the aggregate -- it should just show up with nulls.
    body = client.get('/api/book', headers=auth_headers).get_json()
    row = body['clients'][0]
    assert row['aum'] is None
    assert row['performance'] is None
    assert row['lastReport'] is None

def test_book_counts_reports_distributed_this_month(client, auth_headers, sample_client):
    created = client.post('/api/reports', headers=auth_headers, json={'title': 'Q3 Update', 'client_id': sample_client})
    report_id = created.get_json()['id']
    client.post(f'/api/reports/{report_id}/submit', headers=auth_headers)
    client.post(f'/api/reports/{report_id}/approve', headers=auth_headers)
    client.post(f'/api/reports/{report_id}/distribute', headers=auth_headers)

    body = client.get('/api/book', headers=auth_headers).get_json()
    assert body['reportsDeliveredMtd'] == 1
    assert body['clients'][0]['lastReport']['title'] == 'Q3 Update'
    assert body['clients'][0]['lastReport']['isDistributed'] is True

def test_book_client_drilldown(client, auth_headers, sample_client, sample_holding, sample_performance):
    response = client.get(f'/api/book/{sample_client}', headers=auth_headers)
    assert response.status_code == 200
    body = response.get_json()
    assert body['aum'] == 17500.00
    assert len(body['holdings']) == 1
    assert body['holdings'][0]['security_name'] == 'Apple Inc.'
    assert len(body['performance']) == 1

def test_book_client_drilldown_unknown_client_404s(client, auth_headers):
    response = client.get('/api/book/999999', headers=auth_headers)
    assert response.status_code == 404

def test_book_requires_staff_role(client, client_portal_headers):
    response = client.get('/api/book', headers=client_portal_headers)
    assert response.status_code == 403


# ---------- Phase 4c: scope, relationship manager, risk badge ----------

def _client_named(app, name, manager_id=None):
    from models import Client
    with app.app_context():
        record = Client(name=name, contact_email=f'{name.lower().replace(" ", "")}@example.com',
                        relationship_manager_id=manager_id)
        db_session.add(record)
        db_session.commit()
        return record.id


def test_book_defaults_to_the_whole_firm(client, auth_headers, app, sample_client):
    _client_named(app, 'Unowned Client')
    body = client.get('/api/book', headers=auth_headers).get_json()
    assert body['scope'] == 'firm'
    assert body['clientCount'] >= 2


def test_scope_mine_returns_only_the_callers_clients(client, auth_headers, app):
    from models import User
    with app.app_context():
        me = db_session.query(User).filter_by(email='admin@example.com').first()
        my_id = me.id
    _client_named(app, 'Mine', manager_id=my_id)
    _client_named(app, 'Someone Elses', manager_id=None)

    body = client.get('/api/book?scope=mine', headers=auth_headers).get_json()
    assert body['scope'] == 'mine'
    assert [row['client']['name'] for row in body['clients']] == ['Mine']
    # The header totals describe the scoped set, not the firm -- a "my book"
    # view whose AUM tile still showed the firm's number would be a lie.
    assert body['clientCount'] == 1


def test_scope_mine_can_legitimately_be_empty(client, auth_headers, app):
    _client_named(app, 'Unowned')
    body = client.get('/api/book?scope=mine', headers=auth_headers).get_json()
    assert body['clients'] == []
    assert body['clientCount'] == 0
    assert body['totalAum'] == 0


def test_rows_carry_the_relationship_manager_email(client, auth_headers, app):
    from models import User
    with app.app_context():
        me = db_session.query(User).filter_by(email='admin@example.com').first()
        my_id, my_email = me.id, me.email
    _client_named(app, 'Owned', manager_id=my_id)
    _client_named(app, 'Unowned')

    rows = {r['client']['name']: r for r in client.get('/api/book', headers=auth_headers).get_json()['clients']}
    assert rows['Owned']['relationshipManager'] == my_email
    # Unassigned stays null rather than being filled with a placeholder name.
    assert rows['Unowned']['relationshipManager'] is None


def test_every_row_carries_a_computed_risk_status_and_reason(client, auth_headers, sample_client):
    row = client.get('/api/book', headers=auth_headers).get_json()['clients'][0]
    assert row['risk']['status'] in ('on_track', 'watch', 'flagged', 'sla_breached')
    assert 'reason' in row['risk']


def test_a_breached_deadline_shows_up_as_the_rows_risk(client, auth_headers, app, sample_client):
    import datetime
    from models import Report
    with app.app_context():
        db_session.add(Report(
            title='Overdue quarterly', client_id=sample_client, status='draft', created_by=1,
            due_date=datetime.date.today() - datetime.timedelta(days=5),
        ))
        db_session.commit()

    row = next(r for r in client.get('/api/book', headers=auth_headers).get_json()['clients']
               if r['client']['id'] == sample_client)
    assert row['risk']['status'] == 'sla_breached'
    # The reason is the real computed explanation, not generic copy -- the
    # expanded row's banner shows it verbatim.
    assert 'Overdue quarterly' in row['risk']['reason']


def test_drill_down_carries_the_same_manager_and_risk_fields(client, auth_headers, sample_client):
    body = client.get(f'/api/book/{sample_client}', headers=auth_headers).get_json()
    assert 'relationshipManager' in body
    assert body['risk']['status'] in ('on_track', 'watch', 'flagged', 'sla_breached')
