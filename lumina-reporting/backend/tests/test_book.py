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
