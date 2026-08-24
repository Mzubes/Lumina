def test_health(client):
    response = client.get('/api/health')
    assert response.status_code == 200
    assert response.get_json() == {'status': 'ok'}

def test_login_rejects_invalid_credentials(client):
    response = client.post('/api/auth/login', json={'email': 'admin@example.com', 'password': 'wrong'})
    assert response.status_code == 401

def test_dashboard_requires_authentication(client):
    assert client.get('/api/dashboard').status_code == 401

def test_dashboard_returns_data(client, auth_headers):
    response = client.get('/api/dashboard', headers=auth_headers)
    assert response.status_code == 200
    assert response.get_json()['pendingApprovals'] == 1

def test_fund_round_trip(client, auth_headers):
    created = client.post('/api/funds', headers=auth_headers, json={
        'name': 'Global Equity Strategy', 'asset_class': 'Public Equity',
    })
    assert created.status_code == 201
    listed = client.get('/api/funds', headers=auth_headers)
    assert listed.status_code == 200
    assert listed.get_json()[0]['name'] == 'Global Equity Strategy'

def test_report_generation(client, auth_headers):
    response = client.post('/api/generate_report', headers=auth_headers, json={
        'fund_id': 'test', 'name': 'Test Fund',
    })
    assert response.status_code == 200
    assert response.get_json()['report_id'].endswith('/report_test.pdf')
