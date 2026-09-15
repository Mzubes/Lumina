def test_create_client_requires_editor_or_admin(client, viewer_headers):
    response = client.post('/api/clients', headers=viewer_headers, json={'name': 'New Client'})
    assert response.status_code == 403

def test_create_update_and_list_clients(client, editor_headers):
    created = client.post('/api/clients', headers=editor_headers, json={
        'name': 'Meridian Capital', 'contact_email': 'ir@meridian.example',
    })
    assert created.status_code == 201
    client_id = created.get_json()['id']

    updated = client.put(f'/api/clients/{client_id}', headers=editor_headers, json={'name': 'Meridian Capital Partners'})
    assert updated.status_code == 200
    assert updated.get_json()['name'] == 'Meridian Capital Partners'

    listed = client.get('/api/clients', headers=editor_headers)
    assert any(c['name'] == 'Meridian Capital Partners' for c in listed.get_json())

def test_delete_client_in_use_is_blocked(client, auth_headers, sample_client):
    client.post('/api/reports', headers=auth_headers, json={'title': 'Report', 'client_id': sample_client})
    response = client.delete(f'/api/clients/{sample_client}', headers=auth_headers)
    assert response.status_code == 409

def test_delete_client_not_in_use(client, auth_headers):
    created = client.post('/api/clients', headers=auth_headers, json={'name': 'Disposable Client'}).get_json()
    response = client.delete(f"/api/clients/{created['id']}", headers=auth_headers)
    assert response.status_code == 204

def test_contact_crud_scoped_to_client(client, editor_headers, sample_client):
    created = client.post(f'/api/clients/{sample_client}/contacts', headers=editor_headers, json={
        'name': 'James Brooke', 'email': 'james@acme.example', 'title': 'CIO',
    })
    assert created.status_code == 201
    contact_id = created.get_json()['id']

    listed = client.get(f'/api/clients/{sample_client}/contacts', headers=editor_headers)
    assert len(listed.get_json()) == 1
    assert listed.get_json()[0]['name'] == 'James Brooke'

    updated = client.put(f'/api/clients/{sample_client}/contacts/{contact_id}', headers=editor_headers, json={'title': 'CEO'})
    assert updated.status_code == 200
    assert updated.get_json()['title'] == 'CEO'

    deleted = client.delete(f'/api/clients/{sample_client}/contacts/{contact_id}', headers=editor_headers)
    assert deleted.status_code == 204
    assert client.get(f'/api/clients/{sample_client}/contacts', headers=editor_headers).get_json() == []

def test_contact_not_visible_under_wrong_client(client, editor_headers, sample_client):
    other_client = client.post('/api/clients', headers=editor_headers, json={'name': 'Other Client'}).get_json()
    contact = client.post(f'/api/clients/{sample_client}/contacts', headers=editor_headers, json={'name': 'James Brooke'}).get_json()

    response = client.put(
        f"/api/clients/{other_client['id']}/contacts/{contact['id']}", headers=editor_headers, json={'name': 'Hijacked'},
    )
    assert response.status_code == 404

def test_create_contact_requires_existing_client(client, editor_headers):
    response = client.post('/api/clients/999999/contacts', headers=editor_headers, json={'name': 'Ghost Contact'})
    assert response.status_code == 404
