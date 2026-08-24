import os
import sys

import pytest

BACKEND_DIR = os.path.dirname(os.path.dirname(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app import create_app
from database import db_session
from models import User

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

@pytest.fixture()
def auth_headers(client):
    response = client.post('/api/auth/login', json={
        'email': 'admin@example.com',
        'password': 'correct-horse-battery-staple',
    })
    token = response.get_json()['token']
    return {'Authorization': f'Bearer {token}'}
