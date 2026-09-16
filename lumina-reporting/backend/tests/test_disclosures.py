def test_create_disclosure_requires_editor_or_admin(client, viewer_headers):
    response = client.post('/api/disclosures', headers=viewer_headers, json={
        'title': 'General Risk', 'body': 'All investments involve risk.',
    })
    assert response.status_code == 403

def test_create_and_list_disclosures(client, editor_headers):
    created = client.post('/api/disclosures', headers=editor_headers, json={
        'title': 'General Risk', 'body': 'All investments involve risk.', 'category': 'General',
    })
    assert created.status_code == 201
    body = created.get_json()
    assert body['title'] == 'General Risk'
    assert body['category'] == 'General'

    listed = client.get('/api/disclosures', headers=editor_headers)
    assert listed.status_code == 200
    assert any(d['title'] == 'General Risk' for d in listed.get_json())

def test_create_disclosure_requires_title_and_body(client, editor_headers):
    response = client.post('/api/disclosures', headers=editor_headers, json={'title': 'Missing body'})
    assert response.status_code == 400

def test_compliance_role_can_manage_disclosures(client, compliance_headers):
    response = client.post('/api/disclosures', headers=compliance_headers, json={
        'title': 'Small-Cap Risk', 'body': 'Small-cap investments involve additional risk.',
    })
    assert response.status_code == 201

def test_update_disclosure(client, editor_headers):
    created = client.post('/api/disclosures', headers=editor_headers, json={
        'title': 'Draft', 'body': 'Original text.',
    }).get_json()
    updated = client.put(f"/api/disclosures/{created['id']}", headers=editor_headers, json={'body': 'Revised text.'})
    assert updated.status_code == 200
    assert updated.get_json()['body'] == 'Revised text.'

def test_delete_disclosure_in_use_is_blocked(client, editor_headers):
    disclosure = client.post('/api/disclosures', headers=editor_headers, json={
        'title': 'General Risk', 'body': 'All investments involve risk.',
    }).get_json()
    components = [{"id": "c1", "type": "text_block", "title": "Overview", "data_binding": {"static_text": "x"}}]
    client.post('/api/templates', headers=editor_headers, json={
        'name': 'Factsheet', 'components': components, 'disclosure_ids': [disclosure['id']],
    })

    response = client.delete(f"/api/disclosures/{disclosure['id']}", headers=editor_headers)
    assert response.status_code == 409

def test_disclosure_appears_in_resolved_report_content(app, client, editor_headers, sample_client):
    disclosure = client.post('/api/disclosures', headers=editor_headers, json={
        'title': 'General Risk', 'body': 'All investments involve risk, including loss of principal.',
    }).get_json()
    components = [{"id": "c1", "type": "text_block", "title": "Overview", "data_binding": {"static_text": "Fund overview."}}]
    template = client.post('/api/templates', headers=editor_headers, json={
        'name': 'Factsheet', 'components': components, 'disclosure_ids': [disclosure['id']],
    }).get_json()

    report = client.post('/api/reports', headers=editor_headers, json={
        'title': 'Q3 Factsheet', 'client_id': sample_client, 'template_id': template['id'],
    }).get_json()

    content = client.get(f"/api/reports/{report['id']}/export?format=raw&raw_format=json", headers=editor_headers).get_json()
    titles = [c['title'] for c in content['components']]
    assert 'General Risk' in titles
    disclosure_component = next(c for c in content['components'] if c['title'] == 'General Risk')
    assert disclosure_component['text'] == 'All investments involve risk, including loss of principal.'
