def test_portfolio_requires_client_id_for_staff(client, auth_headers):
    response = client.get('/api/portfolio', headers=auth_headers)
    assert response.status_code == 400

def test_portfolio_staff_can_pass_client_id(client, auth_headers, sample_client, sample_holding, sample_performance):
    response = client.get(f'/api/portfolio?client_id={sample_client}', headers=auth_headers)
    assert response.status_code == 200
    body = response.get_json()
    assert body['asOfDate'] == '2026-06-30'
    assert len(body['holdings']) == 1
    assert body['holdings'][0]['security_id'] == 'AAPL'
    assert len(body['performance']) == 1
    assert body['performance'][0]['period_type'] == 'QTD'

def test_portfolio_client_scoped_to_own_data(
    client, client_portal_headers, other_client_portal_headers, sample_holding, sample_performance,
):
    own = client.get('/api/portfolio', headers=client_portal_headers)
    assert own.status_code == 200
    assert len(own.get_json()['holdings']) == 1

    other = client.get('/api/portfolio', headers=other_client_portal_headers)
    assert other.status_code == 200
    assert other.get_json()['holdings'] == []
    assert other.get_json()['performance'] == []
    assert other.get_json()['asOfDate'] is None

def test_portfolio_requires_auth(client):
    assert client.get('/api/portfolio').status_code == 401
