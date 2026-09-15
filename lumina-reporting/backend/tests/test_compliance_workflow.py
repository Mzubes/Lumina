def _create_report(client, headers, sample_client, **overrides):
    payload = {'title': 'Untitled Report', 'client_id': sample_client}
    payload.update(overrides)
    response = client.post('/api/reports', headers=headers, json=payload)
    assert response.status_code == 201
    return response.get_json()

def test_compliance_required_type_routes_through_compliance(client, auth_headers, sample_client):
    report = _create_report(client, auth_headers, sample_client, report_type='factsheet')
    report_id = report['id']

    client.post(f'/api/reports/{report_id}/submit', headers=auth_headers)
    approved = client.post(f'/api/reports/{report_id}/approve', headers=auth_headers)
    assert approved.status_code == 200
    assert approved.get_json()['status'] == 'compliance'

def test_internal_type_skips_compliance(client, auth_headers, sample_client):
    report = _create_report(client, auth_headers, sample_client, report_type='performance')
    report_id = report['id']

    client.post(f'/api/reports/{report_id}/submit', headers=auth_headers)
    approved = client.post(f'/api/reports/{report_id}/approve', headers=auth_headers)
    assert approved.status_code == 200
    assert approved.get_json()['status'] == 'approved'

def test_report_with_no_type_skips_compliance(client, auth_headers, sample_client):
    report = _create_report(client, auth_headers, sample_client)
    report_id = report['id']

    client.post(f'/api/reports/{report_id}/submit', headers=auth_headers)
    approved = client.post(f'/api/reports/{report_id}/approve', headers=auth_headers)
    assert approved.get_json()['status'] == 'approved'

def test_certify_moves_to_approved(client, auth_headers, compliance_headers, sample_client):
    report = _create_report(client, auth_headers, sample_client, report_type='pitchbook')
    report_id = report['id']
    client.post(f'/api/reports/{report_id}/submit', headers=auth_headers)
    client.post(f'/api/reports/{report_id}/approve', headers=auth_headers)

    certified = client.post(f'/api/reports/{report_id}/certify', headers=compliance_headers)
    assert certified.status_code == 200
    assert certified.get_json()['status'] == 'approved'

def test_request_changes_returns_to_draft(client, auth_headers, compliance_headers, sample_client):
    report = _create_report(client, auth_headers, sample_client, report_type='marketing')
    report_id = report['id']
    client.post(f'/api/reports/{report_id}/submit', headers=auth_headers)
    client.post(f'/api/reports/{report_id}/approve', headers=auth_headers)

    sent_back = client.post(
        f'/api/reports/{report_id}/request-changes', headers=compliance_headers, json={'note': 'Fix the disclosures'},
    )
    assert sent_back.status_code == 200
    assert sent_back.get_json()['status'] == 'draft'

    history = client.get(f'/api/reports/{report_id}/history', headers=auth_headers).get_json()
    assert history[-1]['from_status'] == 'compliance'
    assert history[-1]['to_status'] == 'draft'
    assert history[-1]['note'] == 'Fix the disclosures'

def test_admin_cannot_certify(client, auth_headers, sample_client):
    report = _create_report(client, auth_headers, sample_client, report_type='pitchbook')
    report_id = report['id']
    client.post(f'/api/reports/{report_id}/submit', headers=auth_headers)
    client.post(f'/api/reports/{report_id}/approve', headers=auth_headers)

    response = client.post(f'/api/reports/{report_id}/certify', headers=auth_headers)
    assert response.status_code == 403

def test_compliance_cannot_certify_from_review(client, auth_headers, compliance_headers, sample_client):
    report = _create_report(client, auth_headers, sample_client, report_type='pitchbook')
    report_id = report['id']
    client.post(f'/api/reports/{report_id}/submit', headers=auth_headers)

    response = client.post(f'/api/reports/{report_id}/certify', headers=compliance_headers)
    assert response.status_code == 409

def test_get_report_includes_compliance_required_flag(client, auth_headers, sample_client):
    factsheet = _create_report(client, auth_headers, sample_client, report_type='factsheet')
    performance = _create_report(client, auth_headers, sample_client, report_type='performance')

    factsheet_response = client.get(f"/api/reports/{factsheet['id']}", headers=auth_headers)
    assert factsheet_response.get_json()['complianceRequired'] is True

    performance_response = client.get(f"/api/reports/{performance['id']}", headers=auth_headers)
    assert performance_response.get_json()['complianceRequired'] is False

def test_compliance_required_flag_survives_transition_responses(client, auth_headers, sample_client):
    report = _create_report(client, auth_headers, sample_client, report_type='factsheet')
    report_id = report['id']

    submitted = client.post(f'/api/reports/{report_id}/submit', headers=auth_headers)
    assert submitted.get_json()['complianceRequired'] is True

    approved = client.post(f'/api/reports/{report_id}/approve', headers=auth_headers)
    assert approved.get_json()['complianceRequired'] is True

def test_compliance_role_can_read_history(client, auth_headers, compliance_headers, sample_client):
    report = _create_report(client, auth_headers, sample_client, report_type='pitchbook')
    report_id = report['id']
    client.post(f'/api/reports/{report_id}/submit', headers=auth_headers)

    response = client.get(f'/api/reports/{report_id}/history', headers=compliance_headers)
    assert response.status_code == 200
    entry = response.get_json()[0]
    assert entry['actor_email'] == 'admin@example.com'

def test_full_happy_path_through_compliance(client, auth_headers, compliance_headers, sample_client):
    report = _create_report(client, auth_headers, sample_client, report_type='meeting_pack')
    report_id = report['id']

    assert client.post(f'/api/reports/{report_id}/submit', headers=auth_headers).get_json()['status'] == 'review'
    assert client.post(f'/api/reports/{report_id}/approve', headers=auth_headers).get_json()['status'] == 'compliance'
    assert client.post(f'/api/reports/{report_id}/certify', headers=compliance_headers).get_json()['status'] == 'approved'
    assert client.post(f'/api/reports/{report_id}/distribute', headers=auth_headers).get_json()['status'] == 'distributed'
