def test_list_clients_requires_auth(client):
    assert client.get('/api/clients').status_code == 401

def test_list_clients_returns_data(client, auth_headers, sample_client):
    response = client.get('/api/clients', headers=auth_headers)
    assert response.status_code == 200
    names = [c['name'] for c in response.get_json()]
    assert 'Acme Institutional' in names

def test_compliance_role_can_list_clients(client, compliance_headers, sample_client):
    response = client.get('/api/clients', headers=compliance_headers)
    assert response.status_code == 200
