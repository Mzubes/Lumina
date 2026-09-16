import datetime

import pytest

from database import db_session
from models import Holding, PerformanceSnapshot, Report

def test_holding_requires_client_or_fund(app):
    with app.app_context():
        holding = Holding(as_of_date=datetime.date(2026, 6, 30), security_id='AAPL', market_value=100)
        db_session.add(holding)
        with pytest.raises(ValueError):
            db_session.commit()
        db_session.rollback()

def test_holding_can_be_fund_scoped_only(app, sample_fund):
    with app.app_context():
        holding = Holding(
            fund_id=sample_fund, as_of_date=datetime.date(2026, 6, 30),
            security_id='AAPL', security_name='Apple Inc.', market_value=17500, weight_pct=3.3,
        )
        db_session.add(holding)
        db_session.commit()
        assert holding.client_id is None
        assert holding.fund_id == sample_fund

def test_performance_snapshot_requires_client_or_fund(app):
    with app.app_context():
        snapshot = PerformanceSnapshot(as_of_date=datetime.date(2026, 6, 30), period_type='QTD', return_pct=4.2)
        db_session.add(snapshot)
        with pytest.raises(ValueError):
            db_session.commit()
        db_session.rollback()

def test_report_requires_client_or_fund(app):
    with app.app_context():
        report = Report(title='Orphan Report', status='draft', created_by=1)
        db_session.add(report)
        with pytest.raises(ValueError):
            db_session.commit()
        db_session.rollback()

def test_create_report_rejects_neither_client_nor_fund(client, auth_headers):
    response = client.post('/api/reports', headers=auth_headers, json={'title': 'Orphan Report'})
    assert response.status_code == 400

def test_create_fund_scoped_report_via_api(client, auth_headers, sample_fund):
    response = client.post('/api/reports', headers=auth_headers, json={
        'title': 'Global Small Cap Factsheet', 'fund_id': sample_fund, 'report_type': 'factsheet',
    })
    assert response.status_code == 201
    body = response.get_json()
    assert body['client_id'] is None
    assert body['fund_id'] == sample_fund

def test_create_report_rejects_unknown_fund_id(client, auth_headers):
    response = client.post('/api/reports', headers=auth_headers, json={'title': 'Report', 'fund_id': 999999})
    assert response.status_code == 400

def test_fund_scoped_holdings_and_performance_resolve_in_report(app, client, editor_headers, sample_fund):
    with app.app_context():
        db_session.add(Holding(
            fund_id=sample_fund, as_of_date=datetime.date(2026, 7, 31),
            security_id='SPZN', security_name='Spectrum Brands Holdings Inc.',
            asset_class='Equity', market_value=330000, weight_pct=3.3,
        ))
        db_session.add(PerformanceSnapshot(
            fund_id=sample_fund, as_of_date=datetime.date(2026, 7, 31),
            period_type='YTD', return_pct=18.2, benchmark_return_pct=13.8,
        ))
        db_session.commit()

    components = [
        {"id": "c1", "type": "holdings_table", "title": "Top Holdings",
         "data_binding": {"dataset": "holdings", "filters": {"as_of": "latest"}}},
        {"id": "c2", "type": "performance_summary", "title": "Performance",
         "data_binding": {"dataset": "performance", "filters": {"period_types": ["YTD"]}}},
    ]
    template = client.post('/api/templates', headers=editor_headers, json={
        'name': 'Fund Factsheet Template', 'components': components,
    }).get_json()
    report = client.post('/api/reports', headers=editor_headers, json={
        'title': 'Global Small Cap Factsheet', 'fund_id': sample_fund, 'template_id': template['id'],
    }).get_json()

    content = client.get(
        f"/api/reports/{report['id']}/export?format=raw&raw_format=json", headers=editor_headers,
    ).get_json()
    holdings_component = content['components'][0]
    assert holdings_component['rows'] == [['Spectrum Brands Holdings Inc.', 'Equity', '', 330000.0, 3.3]]
    performance_component = content['components'][1]
    assert performance_component['rows'] == [['YTD', 18.2, 13.8]]
