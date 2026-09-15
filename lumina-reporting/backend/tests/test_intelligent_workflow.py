REVIEWABLE_COMPONENTS = [
    {"id": "c1", "type": "text_block", "title": "Disclosures", "review_role": "compliance",
     "data_binding": {"static_text": "All investments involve risk."}},
    {"id": "c2", "type": "text_block", "title": "Commentary",
     "data_binding": {"static_text": "Markets were steady this quarter."}},
]

def _create_template(client, headers, components=REVIEWABLE_COMPONENTS, name='Reviewed Factsheet'):
    return client.post('/api/templates', headers=headers, json={
        'name': name, 'components': components,
    }).get_json()

def _create_templated_report(client, headers, sample_client, template_id):
    return client.post('/api/reports', headers=headers, json={
        'title': 'Q2 Report', 'client_id': sample_client, 'template_id': template_id,
    }).get_json()

def test_create_template_rejects_invalid_review_role(client, editor_headers):
    components = [{"id": "c1", "type": "text_block", "title": "Disclosures", "review_role": "viewer",
                   "data_binding": {"static_text": "x"}}]
    response = client.post('/api/templates', headers=editor_headers, json={'name': 'Bad', 'components': components})
    assert response.status_code == 400

def test_create_template_accepts_valid_review_role(client, editor_headers):
    template = _create_template(client, editor_headers)
    assert template['components'][0]['review_role'] == 'compliance'
    assert 'review_role' not in template['components'][1] or template['components'][1].get('review_role') is None

def test_review_checklist_only_lists_tagged_components(client, editor_headers, auth_headers, sample_client):
    template = _create_template(client, editor_headers)
    report = _create_templated_report(client, auth_headers, sample_client, template['id'])

    response = client.get(f"/api/reports/{report['id']}/review-checklist", headers=auth_headers)
    assert response.status_code == 200
    checklist = response.get_json()
    assert len(checklist) == 1
    assert checklist[0]['component_id'] == 'c1'
    assert checklist[0]['review_role'] == 'compliance'
    assert checklist[0]['reviewed'] is False

def test_review_checklist_empty_for_legacy_report(client, auth_headers, sample_client):
    legacy = client.post('/api/reports', headers=auth_headers, json={
        'title': 'Legacy Report', 'client_id': sample_client,
    }).get_json()
    response = client.get(f"/api/reports/{legacy['id']}/review-checklist", headers=auth_headers)
    assert response.status_code == 200
    assert response.get_json() == []

def test_mark_component_reviewed_requires_matching_role(client, editor_headers, auth_headers, sample_client):
    template = _create_template(client, editor_headers)
    report = _create_templated_report(client, auth_headers, sample_client, template['id'])

    # editor is not 'compliance' and not 'admin' -> forbidden
    denied = client.post(
        f"/api/reports/{report['id']}/components/c1/review", headers=editor_headers,
    )
    assert denied.status_code == 403

def test_mark_component_reviewed_by_required_role(client, editor_headers, auth_headers, compliance_headers, sample_client):
    template = _create_template(client, editor_headers)
    report = _create_templated_report(client, auth_headers, sample_client, template['id'])

    response = client.post(
        f"/api/reports/{report['id']}/components/c1/review", headers=compliance_headers, json={'note': 'looks good'},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body['component_id'] == 'c1'
    assert body['note'] == 'looks good'

    checklist = client.get(f"/api/reports/{report['id']}/review-checklist", headers=auth_headers).get_json()
    assert checklist[0]['reviewed'] is True

def test_mark_component_reviewed_by_admin_override(client, editor_headers, auth_headers, sample_client):
    template = _create_template(client, editor_headers)
    report = _create_templated_report(client, auth_headers, sample_client, template['id'])

    response = client.post(f"/api/reports/{report['id']}/components/c1/review", headers=auth_headers)
    assert response.status_code == 200

def test_mark_component_reviewed_rejects_unknown_component(client, editor_headers, auth_headers, sample_client):
    template = _create_template(client, editor_headers)
    report = _create_templated_report(client, auth_headers, sample_client, template['id'])

    # c2 has no review_role -> not reviewable
    response = client.post(f"/api/reports/{report['id']}/components/c2/review", headers=auth_headers)
    assert response.status_code == 404

def test_clear_component_review(client, editor_headers, auth_headers, compliance_headers, sample_client):
    template = _create_template(client, editor_headers)
    report = _create_templated_report(client, auth_headers, sample_client, template['id'])

    client.post(f"/api/reports/{report['id']}/components/c1/review", headers=compliance_headers)
    cleared = client.delete(f"/api/reports/{report['id']}/components/c1/review", headers=compliance_headers)
    assert cleared.status_code == 204

    checklist = client.get(f"/api/reports/{report['id']}/review-checklist", headers=auth_headers).get_json()
    assert checklist[0]['reviewed'] is False

def test_template_client_assignment_crud(client, editor_headers, auth_headers, sample_client):
    template = _create_template(client, editor_headers)

    empty = client.get(f"/api/templates/{template['id']}/clients", headers=auth_headers)
    assert empty.get_json() == []

    set_response = client.put(
        f"/api/templates/{template['id']}/clients", headers=editor_headers,
        json={'client_ids': [sample_client]},
    )
    assert set_response.status_code == 200
    assert set_response.get_json() == [sample_client]

def test_template_client_assignment_rejects_unknown_client(client, editor_headers):
    template = _create_template(client, editor_headers)
    response = client.put(
        f"/api/templates/{template['id']}/clients", headers=editor_headers,
        json={'client_ids': [999999]},
    )
    assert response.status_code == 400

def test_approve_template_requires_assigned_clients(client, editor_headers, auth_headers):
    template = _create_template(client, editor_headers)
    response = client.post(f"/api/templates/{template['id']}/approve", headers=auth_headers)
    assert response.status_code == 400

def test_approve_template_generates_one_report_per_client(client, editor_headers, auth_headers, sample_client):
    template = _create_template(client, editor_headers)
    client.put(
        f"/api/templates/{template['id']}/clients", headers=editor_headers,
        json={'client_ids': [sample_client]},
    )

    response = client.post(f"/api/templates/{template['id']}/approve", headers=auth_headers)
    assert response.status_code == 200
    body = response.get_json()
    assert body['template']['approved_at'] is not None
    assert len(body['generated_reports']) == 1
    generated = body['generated_reports'][0]
    assert generated['client_id'] == sample_client
    assert generated['template_id'] == template['id']
    assert generated['status'] == 'draft'

    # the generated report is an ordinary report -- it goes through the
    # normal workflow independently, nothing about fan-out shortcuts it.
    submit = client.post(f"/api/reports/{generated['id']}/submit", headers=auth_headers)
    assert submit.status_code == 200
    assert submit.get_json()['status'] == 'review'

def test_approve_template_requires_admin(client, editor_headers, sample_client):
    template = _create_template(client, editor_headers)
    client.put(
        f"/api/templates/{template['id']}/clients", headers=editor_headers,
        json={'client_ids': [sample_client]},
    )
    response = client.post(f"/api/templates/{template['id']}/approve", headers=editor_headers)
    assert response.status_code == 403

def test_reapproving_template_creates_fresh_batch(client, editor_headers, auth_headers, sample_client):
    template = _create_template(client, editor_headers)
    client.put(
        f"/api/templates/{template['id']}/clients", headers=editor_headers,
        json={'client_ids': [sample_client]},
    )
    first = client.post(f"/api/templates/{template['id']}/approve", headers=auth_headers).get_json()
    second = client.post(f"/api/templates/{template['id']}/approve", headers=auth_headers).get_json()
    assert len(first['generated_reports']) == 1
    assert len(second['generated_reports']) == 1
    assert first['generated_reports'][0]['id'] != second['generated_reports'][0]['id']
