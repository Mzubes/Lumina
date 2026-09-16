import json

from database import db_session
from models import ReportTemplate, WorkflowDiagram

def _user_id(client, auth_headers, email):
    users = client.get('/api/users', headers=auth_headers).get_json()
    return next(u['id'] for u in users if u['email'] == email)

def _create_group(client, auth_headers, name='Compliance', description=None):
    response = client.post('/api/workflow-groups', headers=auth_headers, json={'name': name, 'description': description})
    assert response.status_code == 201
    return response.get_json()

# ---------- CRUD ----------

def test_list_groups_open_to_staff_but_not_client(client, auth_headers, viewer_headers, client_portal_headers):
    assert client.get('/api/workflow-groups', headers=viewer_headers).status_code == 200
    assert client.get('/api/workflow-groups', headers=client_portal_headers).status_code == 403

def test_create_group_requires_admin(client, editor_headers, viewer_headers):
    payload = {'name': 'Compliance'}
    assert client.post('/api/workflow-groups', headers=editor_headers, json=payload).status_code == 403
    assert client.post('/api/workflow-groups', headers=viewer_headers, json=payload).status_code == 403

def test_create_group_success(client, auth_headers):
    group = _create_group(client, auth_headers, name='Compliance', description='Final sign-off')
    assert group['name'] == 'Compliance'
    assert group['description'] == 'Final sign-off'
    assert group['color'].startswith('cat-')

    listed = client.get('/api/workflow-groups', headers=auth_headers).get_json()
    assert listed == [{**group, 'member_count': 0}]

def test_create_group_rejects_duplicate_name(client, auth_headers):
    _create_group(client, auth_headers, name='Compliance')
    response = client.post('/api/workflow-groups', headers=auth_headers, json={'name': 'Compliance'})
    assert response.status_code == 400

def test_create_group_rejects_blank_name(client, auth_headers):
    response = client.post('/api/workflow-groups', headers=auth_headers, json={'name': '  '})
    assert response.status_code == 400

def test_update_group_rename(client, auth_headers):
    group = _create_group(client, auth_headers, name='Compliance')
    response = client.put(f"/api/workflow-groups/{group['id']}", headers=auth_headers, json={'name': 'Legal & Compliance'})
    assert response.status_code == 200
    assert response.get_json()['name'] == 'Legal & Compliance'

def test_update_group_rejects_duplicate_name(client, auth_headers):
    _create_group(client, auth_headers, name='Compliance')
    other = _create_group(client, auth_headers, name='Client Reporting')
    response = client.put(f"/api/workflow-groups/{other['id']}", headers=auth_headers, json={'name': 'Compliance'})
    assert response.status_code == 400

def test_update_group_requires_admin(client, auth_headers, editor_headers):
    group = _create_group(client, auth_headers, name='Compliance')
    response = client.put(f"/api/workflow-groups/{group['id']}", headers=editor_headers, json={'name': 'Renamed'})
    assert response.status_code == 403

def test_delete_group_success(client, auth_headers):
    group = _create_group(client, auth_headers, name='Compliance')
    response = client.delete(f"/api/workflow-groups/{group['id']}", headers=auth_headers)
    assert response.status_code == 204
    assert client.get('/api/workflow-groups', headers=auth_headers).get_json() == []

def test_delete_group_blocked_when_referenced_by_active_diagram(app, client, auth_headers, sample_template):
    group = _create_group(client, auth_headers, name='Compliance')
    with app.app_context():
        template = db_session.query(ReportTemplate).filter_by(id=sample_template).first()
        template.name = 'Quarterly Factsheet'
        nodes = [{'id': 'n1', 'name': 'Sign-off', 'type': 'step', 'group_id': group['id'], 'position': {'x': 0, 'y': 0}}]
        diagram = WorkflowDiagram(
            template_id=sample_template, version=1, is_active=True,
            nodes=json.dumps(nodes), edges=json.dumps([]), generated=False, created_by=1,
        )
        db_session.add(diagram)
        db_session.commit()

    response = client.delete(f"/api/workflow-groups/{group['id']}", headers=auth_headers)
    assert response.status_code == 409
    assert 'Quarterly Factsheet' in response.get_json()['message']

def test_delete_group_requires_admin(client, auth_headers, editor_headers):
    group = _create_group(client, auth_headers, name='Compliance')
    response = client.delete(f"/api/workflow-groups/{group['id']}", headers=editor_headers)
    assert response.status_code == 403

def test_delete_group_404_for_unknown_id(client, auth_headers):
    assert client.delete('/api/workflow-groups/999', headers=auth_headers).status_code == 404

# ---------- membership ----------

def test_add_list_and_remove_member(client, auth_headers, editor_headers):
    group = _create_group(client, auth_headers, name='Compliance')
    editor_id = _user_id(client, auth_headers, 'editor@example.com')

    add = client.post(f"/api/workflow-groups/{group['id']}/members", headers=auth_headers, json={'user_id': editor_id})
    assert add.status_code == 201

    members = client.get(f"/api/workflow-groups/{group['id']}/members", headers=auth_headers).get_json()
    assert [m['id'] for m in members] == [editor_id]

    listed = client.get('/api/workflow-groups', headers=auth_headers).get_json()
    assert listed[0]['member_count'] == 1

    remove = client.delete(f"/api/workflow-groups/{group['id']}/members/{editor_id}", headers=auth_headers)
    assert remove.status_code == 204
    assert client.get(f"/api/workflow-groups/{group['id']}/members", headers=auth_headers).get_json() == []

def test_add_member_rejects_duplicate(client, auth_headers, editor_headers):
    group = _create_group(client, auth_headers, name='Compliance')
    editor_id = _user_id(client, auth_headers, 'editor@example.com')
    client.post(f"/api/workflow-groups/{group['id']}/members", headers=auth_headers, json={'user_id': editor_id})

    response = client.post(f"/api/workflow-groups/{group['id']}/members", headers=auth_headers, json={'user_id': editor_id})
    assert response.status_code == 400

def test_add_member_rejects_unknown_user(client, auth_headers):
    group = _create_group(client, auth_headers, name='Compliance')
    response = client.post(f"/api/workflow-groups/{group['id']}/members", headers=auth_headers, json={'user_id': 999})
    assert response.status_code == 400

def test_add_member_requires_admin(client, auth_headers, editor_headers):
    group = _create_group(client, auth_headers, name='Compliance')
    editor_id = _user_id(client, auth_headers, 'editor@example.com')
    response = client.post(f"/api/workflow-groups/{group['id']}/members", headers=editor_headers, json={'user_id': editor_id})
    assert response.status_code == 403

def test_list_members_open_to_viewer(client, auth_headers, viewer_headers):
    group = _create_group(client, auth_headers, name='Compliance')
    response = client.get(f"/api/workflow-groups/{group['id']}/members", headers=viewer_headers)
    assert response.status_code == 200
