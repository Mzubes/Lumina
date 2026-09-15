REVIEWABLE_COMPONENTS = [
    {"id": "c1", "type": "text_block", "title": "Disclosures", "review_role": "compliance",
     "data_binding": {"static_text": "All investments involve risk."}},
]

ADMIN_REVIEWABLE_COMPONENTS = [
    {"id": "c1", "type": "text_block", "title": "Firm Overview", "review_role": "admin",
     "data_binding": {"static_text": "Firm overview text."}},
]

EDITOR_REVIEWABLE_COMPONENTS = [
    {"id": "c1", "type": "text_block", "title": "Commentary", "review_role": "editor",
     "data_binding": {"static_text": "Commentary text."}},
]

def _create_template(client, editor_headers, components, name='Queue Template'):
    return client.post('/api/templates', headers=editor_headers, json={
        'name': name, 'components': components,
    }).get_json()

def _create_templated_report(client, auth_headers, sample_client, template_id, title='Queue Report', report_type=None):
    payload = {'title': title, 'client_id': sample_client, 'template_id': template_id}
    if report_type:
        payload['report_type'] = report_type
    return client.post('/api/reports', headers=auth_headers, json=payload).get_json()

def test_my_queue_requires_actionable_role(client, viewer_headers, client_portal_headers):
    assert client.get('/api/reports/my-queue', headers=viewer_headers).status_code == 403
    assert client.get('/api/reports/my-queue', headers=client_portal_headers).status_code == 403

def test_my_queue_admin_sees_review_status_reports_with_approval_reason(client, editor_headers, auth_headers, sample_client):
    template = _create_template(client, editor_headers, REVIEWABLE_COMPONENTS)
    report = _create_templated_report(client, auth_headers, sample_client, template['id'])
    client.post(f"/api/reports/{report['id']}/submit", headers=auth_headers)

    body = client.get('/api/reports/my-queue', headers=auth_headers).get_json()
    assert len(body) == 1
    assert body[0]['id'] == report['id']
    reasons = {r['type']: r for r in body[0]['reasons']}
    assert reasons['approval']['label'] == 'Needs your approval'
    # admin can review ANY component regardless of its own review_role (the
    # same always-allowed override mark_component_reviewed already grants).
    assert 'component_review' in reasons

def test_my_queue_compliance_sees_compliance_status_reports_with_reason(client, editor_headers, auth_headers, compliance_headers, sample_client):
    template = _create_template(client, editor_headers, REVIEWABLE_COMPONENTS)
    report = _create_templated_report(client, auth_headers, sample_client, template['id'], report_type='factsheet')
    client.post(f"/api/reports/{report['id']}/submit", headers=auth_headers)
    client.post(f"/api/reports/{report['id']}/approve", headers=auth_headers)

    body = client.get('/api/reports/my-queue', headers=compliance_headers).get_json()
    assert len(body) == 1
    reasons = {r['type']: r for r in body[0]['reasons']}
    assert reasons['compliance']['label'] == 'Needs your compliance certification'
    assert reasons['component_review']['label'] == '1 component needs your review'
    assert reasons['component_review']['components'] == ['Disclosures']

NON_REVIEWABLE_COMPONENTS = [
    {"id": "c1", "type": "text_block", "title": "Commentary",
     "data_binding": {"static_text": "No review_role on this one."}},
]

def test_my_queue_admin_does_not_see_other_compliance_reports(client, editor_headers, auth_headers, compliance_headers, sample_client):
    # No reviewable components here, so this isolates the 'compliance' reason
    # type itself -- it must never appear for a non-compliance role, even
    # though admin's component-review override could otherwise mask that.
    template = _create_template(client, editor_headers, NON_REVIEWABLE_COMPONENTS)
    report = _create_templated_report(client, auth_headers, sample_client, template['id'], report_type='factsheet')
    client.post(f"/api/reports/{report['id']}/submit", headers=auth_headers)
    client.post(f"/api/reports/{report['id']}/approve", headers=auth_headers)

    body = client.get('/api/reports/my-queue', headers=auth_headers).get_json()
    assert body == []

def test_my_queue_editor_sees_only_component_reviews_assigned_to_editor(client, editor_headers, auth_headers, sample_client):
    template = _create_template(client, editor_headers, EDITOR_REVIEWABLE_COMPONENTS)
    report = _create_templated_report(client, auth_headers, sample_client, template['id'])
    client.post(f"/api/reports/{report['id']}/submit", headers=auth_headers)

    body = client.get('/api/reports/my-queue', headers=editor_headers).get_json()
    assert len(body) == 1
    reasons = {r['type']: r for r in body[0]['reasons']}
    assert reasons.keys() == {'component_review'}
    assert reasons['component_review']['components'] == ['Commentary']

def test_my_queue_report_needing_two_things_from_admin_appears_once(client, editor_headers, auth_headers, sample_client):
    template = _create_template(client, editor_headers, ADMIN_REVIEWABLE_COMPONENTS)
    report = _create_templated_report(client, auth_headers, sample_client, template['id'])
    client.post(f"/api/reports/{report['id']}/submit", headers=auth_headers)

    body = client.get('/api/reports/my-queue', headers=auth_headers).get_json()
    assert len(body) == 1
    reason_types = {r['type'] for r in body[0]['reasons']}
    assert reason_types == {'approval', 'component_review'}

def test_my_queue_excludes_already_reviewed_components(client, editor_headers, auth_headers, compliance_headers, sample_client):
    template = _create_template(client, editor_headers, REVIEWABLE_COMPONENTS)
    report = _create_templated_report(client, auth_headers, sample_client, template['id'], report_type='factsheet')
    client.post(f"/api/reports/{report['id']}/submit", headers=auth_headers)
    client.post(f"/api/reports/{report['id']}/approve", headers=auth_headers)
    client.post(f"/api/reports/{report['id']}/components/c1/review", headers=compliance_headers)

    body = client.get('/api/reports/my-queue', headers=compliance_headers).get_json()
    reasons = {r['type'] for r in body[0]['reasons']}
    assert 'component_review' not in reasons
    assert 'compliance' in reasons
