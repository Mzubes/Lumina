def test_list_users_requires_admin(client, editor_headers, viewer_headers):
    assert client.get('/api/users', headers=editor_headers).status_code == 403
    assert client.get('/api/users', headers=viewer_headers).status_code == 403

def test_list_users_as_admin(client, auth_headers):
    response = client.get('/api/users', headers=auth_headers)
    assert response.status_code == 200
    emails = [u['email'] for u in response.get_json()]
    assert 'admin@example.com' in emails

def test_create_user_requires_admin(client, editor_headers):
    response = client.post('/api/users', headers=editor_headers, json={
        'email': 'new@example.com', 'role': 'viewer', 'password': 'longenough',
    })
    assert response.status_code == 403

def test_create_user_success(client, auth_headers):
    response = client.post('/api/users', headers=auth_headers, json={
        'email': 'NewUser@Example.com', 'role': 'viewer', 'password': 'longenough',
    })
    assert response.status_code == 201
    body = response.get_json()
    assert body['email'] == 'newuser@example.com'
    assert body['role'] == 'viewer'
    assert 'password_hash' not in body
    assert 'password' not in body

def test_new_user_can_log_in(client, auth_headers):
    client.post('/api/users', headers=auth_headers, json={
        'email': 'loginable@example.com', 'role': 'editor', 'password': 'longenough',
    })
    login = client.post('/api/auth/login', json={'email': 'loginable@example.com', 'password': 'longenough'})
    assert login.status_code == 200
    assert login.get_json()['role'] == 'editor'

def test_create_user_rejects_invalid_role(client, auth_headers):
    response = client.post('/api/users', headers=auth_headers, json={
        'email': 'bad@example.com', 'role': 'superuser', 'password': 'longenough',
    })
    assert response.status_code == 400

def test_create_user_rejects_short_password(client, auth_headers):
    response = client.post('/api/users', headers=auth_headers, json={
        'email': 'short@example.com', 'role': 'viewer', 'password': 'short',
    })
    assert response.status_code == 400

def test_create_user_rejects_duplicate_email(client, auth_headers):
    client.post('/api/users', headers=auth_headers, json={
        'email': 'dup@example.com', 'role': 'viewer', 'password': 'longenough',
    })
    response = client.post('/api/users', headers=auth_headers, json={
        'email': 'dup@example.com', 'role': 'editor', 'password': 'longenough',
    })
    assert response.status_code == 400

def test_create_client_role_requires_valid_client_id(client, auth_headers, sample_client):
    missing = client.post('/api/users', headers=auth_headers, json={
        'email': 'clientuser@example.com', 'role': 'client', 'password': 'longenough',
    })
    assert missing.status_code == 400

    unknown = client.post('/api/users', headers=auth_headers, json={
        'email': 'clientuser@example.com', 'role': 'client', 'client_id': 999999, 'password': 'longenough',
    })
    assert unknown.status_code == 400

    valid = client.post('/api/users', headers=auth_headers, json={
        'email': 'clientuser@example.com', 'role': 'client', 'client_id': sample_client, 'password': 'longenough',
    })
    assert valid.status_code == 201
    assert valid.get_json()['client_id'] == sample_client

def test_update_user_role_and_password(client, auth_headers):
    created = client.post('/api/users', headers=auth_headers, json={
        'email': 'update-me@example.com', 'role': 'viewer', 'password': 'longenough',
    }).get_json()

    updated = client.put(f"/api/users/{created['id']}", headers=auth_headers, json={'role': 'editor'})
    assert updated.status_code == 200
    assert updated.get_json()['role'] == 'editor'

    reset = client.put(f"/api/users/{created['id']}", headers=auth_headers, json={'password': 'brandnewpassword'})
    assert reset.status_code == 200
    login = client.post('/api/auth/login', json={'email': 'update-me@example.com', 'password': 'brandnewpassword'})
    assert login.status_code == 200

def test_delete_user(client, auth_headers):
    created = client.post('/api/users', headers=auth_headers, json={
        'email': 'delete-me@example.com', 'role': 'viewer', 'password': 'longenough',
    }).get_json()
    response = client.delete(f"/api/users/{created['id']}", headers=auth_headers)
    assert response.status_code == 204
    assert client.get(f"/api/users/{created['id']}", headers=auth_headers).status_code == 404

def test_cannot_delete_self(client, auth_headers):
    admin = next(u for u in client.get('/api/users', headers=auth_headers).get_json() if u['email'] == 'admin@example.com')
    response = client.delete(f"/api/users/{admin['id']}", headers=auth_headers)
    assert response.status_code == 400

def test_cannot_delete_last_admin(client, auth_headers, app):
    # The only admin is the one making the request -- covered by
    # test_cannot_delete_self already, so create a second admin, delete the
    # ORIGINAL admin via the second one's session, leaving the second as the
    # sole admin, then confirm deleting/demoting that last admin is refused.
    from database import db_session
    from models import User
    with app.app_context():
        second_admin = User(email='second-admin@example.com', role='admin')
        second_admin.set_password('longenough')
        db_session.add(second_admin)
        db_session.commit()
        second_admin_id = second_admin.id

    second_login = client.post('/api/auth/login', json={'email': 'second-admin@example.com', 'password': 'longenough'}).get_json()
    second_headers = {'Authorization': f"Bearer {second_login['token']}"}

    admin = next(u for u in client.get('/api/users', headers=second_headers).get_json() if u['email'] == 'admin@example.com')
    remove_first = client.delete(f"/api/users/{admin['id']}", headers=second_headers)
    assert remove_first.status_code == 204

    # Now only second_admin remains -- deleting or demoting it must be refused.
    delete_last = client.delete(f"/api/users/{second_admin_id}", headers=second_headers)
    assert delete_last.status_code == 400  # self-delete guard fires first, also correctly refused

    demote_last = client.put(f"/api/users/{second_admin_id}", headers=second_headers, json={'role': 'editor'})
    assert demote_last.status_code == 409
