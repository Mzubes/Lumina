def test_health(client):
    response = client.get('/api/health')
    assert response.status_code == 200
    assert response.get_json() == {'status': 'ok'}

def test_login_rejects_invalid_credentials(client):
    response = client.post('/api/auth/login', json={'email': 'admin@example.com', 'password': 'wrong'})
    assert response.status_code == 401

def test_dashboard_requires_authentication(client):
    assert client.get('/api/dashboard').status_code == 401

def test_dashboard_returns_data(client, auth_headers, sample_client):
    report = client.post('/api/reports', headers=auth_headers, json={
        'title': 'Pending Review Report', 'client_id': sample_client,
    }).get_json()
    client.post(f"/api/reports/{report['id']}/submit", headers=auth_headers)

    response = client.get('/api/dashboard', headers=auth_headers)
    assert response.status_code == 200
    body = response.get_json()
    assert body['pendingApprovals'] == 1
    assert body['pendingCompliance'] == 0
    assert body['totalReports'] == 1
    assert body['reportsByStatus'] == {'draft': 0, 'review': 1, 'compliance': 0, 'approved': 0, 'distributed': 0}
    assert body['reportsByTeam'] == [{'label': 'Unassigned', 'count': 1}]
    assert body['reportsByClient'] == [{'label': 'Acme Institutional', 'count': 1}]
    assert body['failedDataSources'] == []
    assert body['recentReports'][0]['name'] == 'Pending Review Report'

def test_fund_round_trip(client, auth_headers):
    created = client.post('/api/funds', headers=auth_headers, json={
        'name': 'Global Equity Strategy', 'asset_class': 'Public Equity',
    })
    assert created.status_code == 201
    listed = client.get('/api/funds', headers=auth_headers)
    assert listed.status_code == 200
    assert listed.get_json()[0]['name'] == 'Global Equity Strategy'

def test_report_generation(client, auth_headers, sample_client):
    response = client.post('/api/reports', headers=auth_headers, json={
        'title': 'Test Fund Report', 'client_id': sample_client,
    })
    assert response.status_code == 201
    body = response.get_json()
    assert body['status'] == 'draft'
    assert body['file_path'] == f"/static/reports/report_{body['id']}.pdf"
