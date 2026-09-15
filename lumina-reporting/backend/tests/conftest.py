import os
import sys

import pytest

BACKEND_DIR = os.path.dirname(os.path.dirname(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import datetime
import json

from app import create_app
from database import db_session
from models import Client, FundData, Holding, PerformanceSnapshot, ReportTemplate, User

@pytest.fixture()
def app(tmp_path):
    application = create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': f"sqlite:///{tmp_path / 'test.sqlite'}",
        'JWT_SECRET_KEY': 'test-jwt-secret',
        'CORS_ORIGINS': ['http://localhost:3000'],
    })
    with application.app_context():
        user = User(email='admin@example.com', role='admin')
        user.set_password('correct-horse-battery-staple')
        db_session.add(user)
        db_session.commit()
    yield application

@pytest.fixture()
def client(app):
    return app.test_client()

def _login_headers(test_client, email, password):
    response = test_client.post('/api/auth/login', json={'email': email, 'password': password})
    token = response.get_json()['token']
    return {'Authorization': f'Bearer {token}'}

@pytest.fixture()
def auth_headers(client):
    return _login_headers(client, 'admin@example.com', 'correct-horse-battery-staple')

@pytest.fixture()
def editor_headers(app, client):
    with app.app_context():
        user = User(email='editor@example.com', role='editor')
        user.set_password('editor-password')
        db_session.add(user)
        db_session.commit()
    return _login_headers(client, 'editor@example.com', 'editor-password')

@pytest.fixture()
def viewer_headers(app, client):
    with app.app_context():
        user = User(email='viewer@example.com', role='viewer')
        user.set_password('viewer-password')
        db_session.add(user)
        db_session.commit()
    return _login_headers(client, 'viewer@example.com', 'viewer-password')

@pytest.fixture()
def compliance_headers(app, client):
    with app.app_context():
        user = User(email='compliance@example.com', role='compliance')
        user.set_password('compliance-password')
        db_session.add(user)
        db_session.commit()
    return _login_headers(client, 'compliance@example.com', 'compliance-password')

@pytest.fixture()
def sample_client(app):
    with app.app_context():
        institution = Client(name='Acme Institutional', contact_email='ops@acme.example')
        db_session.add(institution)
        db_session.commit()
        return institution.id

@pytest.fixture()
def client_portal_headers(app, client, sample_client):
    with app.app_context():
        user = User(email='client-user@example.com', role='client', client_id=sample_client)
        user.set_password('client-password')
        db_session.add(user)
        db_session.commit()
    return _login_headers(client, 'client-user@example.com', 'client-password')

@pytest.fixture()
def other_client_portal_headers(app, client):
    with app.app_context():
        other = Client(name='Other Institutional', contact_email='ops@other.example')
        db_session.add(other)
        db_session.commit()
        user = User(email='other-client-user@example.com', role='client', client_id=other.id)
        user.set_password('other-client-password')
        db_session.add(user)
        db_session.commit()
    return _login_headers(client, 'other-client-user@example.com', 'other-client-password')

@pytest.fixture()
def sample_fund(app):
    with app.app_context():
        fund = FundData(name='Global Small Cap Focused Value', asset_class='Equity', ticker='PZFVX')
        db_session.add(fund)
        db_session.commit()
        return fund.id

@pytest.fixture()
def sample_holding(app, sample_client):
    with app.app_context():
        holding = Holding(
            client_id=sample_client, as_of_date=datetime.date(2026, 6, 30),
            security_id='AAPL', security_name='Apple Inc.', asset_class='Equity',
            quantity=100, market_value=17500.00, weight_pct=12.5,
        )
        db_session.add(holding)
        db_session.commit()
        return holding.id

@pytest.fixture()
def sample_performance(app, sample_client):
    with app.app_context():
        snapshot = PerformanceSnapshot(
            client_id=sample_client, as_of_date=datetime.date(2026, 6, 30),
            period_type='QTD', return_pct=3.25, benchmark_return_pct=2.90,
        )
        db_session.add(snapshot)
        db_session.commit()
        return snapshot.id

@pytest.fixture()
def sample_template(app):
    components = [
        {"id": "comp-1", "type": "holdings_table", "title": "Portfolio Holdings",
         "data_binding": {"dataset": "holdings", "filters": {"as_of": "latest"}}},
        {"id": "comp-2", "type": "performance_summary", "title": "Performance",
         "data_binding": {"dataset": "performance", "filters": {"period_types": ["QTD"]}}},
        {"id": "comp-3", "type": "text_block", "title": "Commentary",
         "data_binding": {"static_text": "Markets were steady this quarter."}},
    ]
    with app.app_context():
        template = ReportTemplate(
            name='Quarterly Report', components=json.dumps(components), created_by=1,
        )
        db_session.add(template)
        db_session.commit()
        return template.id
