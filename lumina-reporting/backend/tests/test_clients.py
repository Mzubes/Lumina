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

def test_client_can_be_assigned_a_relationship_manager(client, auth_headers, app):
    from database import db_session
    from models import User
    with app.app_context():
        manager_id = db_session.query(User).filter_by(email='admin@example.com').first().id

    created = client.post('/api/clients', headers=auth_headers, json={
        'name': 'Northbridge Capital', 'relationship_manager_id': manager_id,
    })
    assert created.status_code == 201
    assert created.get_json()['relationship_manager_id'] == manager_id

    # Absent key must leave the assignment alone, not silently clear it.
    client_id = created.get_json()['id']
    updated = client.put(f'/api/clients/{client_id}', headers=auth_headers, json={'name': 'Northbridge Capital LP'})
    assert updated.get_json()['relationship_manager_id'] == manager_id

    # An explicit null clears it.
    cleared = client.put(f'/api/clients/{client_id}', headers=auth_headers, json={'relationship_manager_id': None})
    assert cleared.get_json()['relationship_manager_id'] is None

def test_relationship_manager_must_be_a_real_staff_user(client, auth_headers, client_portal_headers, app):
    from database import db_session
    from models import User
    unknown = client.post('/api/clients', headers=auth_headers, json={
        'name': 'Ghost Capital', 'relationship_manager_id': 999999,
    })
    assert unknown.status_code == 400

    with app.app_context():
        portal_user_id = db_session.query(User).filter_by(role='client').first().id
    # The client-portal user is the other side of the relationship, not its owner.
    rejected = client.post('/api/clients', headers=auth_headers, json={
        'name': 'Ghost Capital', 'relationship_manager_id': portal_user_id,
    })
    assert rejected.status_code == 400
