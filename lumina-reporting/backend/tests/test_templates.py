VALID_COMPONENTS = [
    {"id": "comp-1", "type": "holdings_table", "title": "Portfolio Holdings",
     "data_binding": {"dataset": "holdings", "filters": {"as_of": "latest"}}},
    {"id": "comp-2", "type": "text_block", "title": "Commentary",
     "data_binding": {"static_text": "Markets were steady this quarter."}},
]

def test_create_template_requires_editor_or_admin(client, viewer_headers):
    response = client.post('/api/templates', headers=viewer_headers, json={
        'name': 'Quarterly Report', 'components': VALID_COMPONENTS,
    })
    assert response.status_code == 403

def test_create_template_success(client, editor_headers):
    response = client.post('/api/templates', headers=editor_headers, json={
        'name': 'Quarterly Report', 'description': 'Standard quarterly pack',
        'components': VALID_COMPONENTS,
    })
    assert response.status_code == 201
    body = response.get_json()
    assert body['name'] == 'Quarterly Report'
    assert len(body['components']) == 2

def test_create_template_rejects_invalid_type(client, editor_headers):
    bad_components = [{"id": "c1", "type": "bogus_widget", "title": "X", "data_binding": {}}]
    response = client.post('/api/templates', headers=editor_headers, json={
        'name': 'Bad Template', 'components': bad_components,
    })
    assert response.status_code == 400

def test_create_template_rejects_duplicate_ids(client, editor_headers):
    dup_components = [
        {"id": "c1", "type": "text_block", "title": "A", "data_binding": {"static_text": "x"}},
        {"id": "c1", "type": "text_block", "title": "B", "data_binding": {"static_text": "y"}},
    ]
    response = client.post('/api/templates', headers=editor_headers, json={
        'name': 'Dup Template', 'components': dup_components,
    })
    assert response.status_code == 400

def test_create_template_rejects_text_block_without_text(client, editor_headers):
    components = [{"id": "c1", "type": "text_block", "title": "Commentary", "data_binding": {}}]
    response = client.post('/api/templates', headers=editor_headers, json={
        'name': 'Missing Text', 'components': components,
    })
    assert response.status_code == 400

def test_update_and_get_template(client, editor_headers):
    created = client.post('/api/templates', headers=editor_headers, json={
        'name': 'Quarterly Report', 'components': VALID_COMPONENTS,
    }).get_json()

    updated = client.put(f"/api/templates/{created['id']}", headers=editor_headers, json={
        'name': 'Quarterly Report v2', 'components': VALID_COMPONENTS,
    })
    assert updated.status_code == 200
    assert updated.get_json()['name'] == 'Quarterly Report v2'

    fetched = client.get(f"/api/templates/{created['id']}", headers=editor_headers)
    assert fetched.get_json()['name'] == 'Quarterly Report v2'

def test_delete_template_not_in_use(client, editor_headers):
    created = client.post('/api/templates', headers=editor_headers, json={
        'name': 'Disposable', 'components': VALID_COMPONENTS,
    }).get_json()
    response = client.delete(f"/api/templates/{created['id']}", headers=editor_headers)
    assert response.status_code == 204
    assert client.get(f"/api/templates/{created['id']}", headers=editor_headers).status_code == 404

def test_delete_template_in_use_is_blocked(app, client, editor_headers, sample_client):
    created = client.post('/api/templates', headers=editor_headers, json={
        'name': 'In Use Template', 'components': VALID_COMPONENTS,
    }).get_json()

    from database import db_session
    from models import Report
    with app.app_context():
        report = Report(
            title='Report using template', client_id=sample_client,
            template_id=created['id'], status='draft', created_by=1,
        )
        db_session.add(report)
        db_session.commit()

    response = client.delete(f"/api/templates/{created['id']}", headers=editor_headers)
    assert response.status_code == 409
