def _create_report(client, headers, sample_client, title='Q3 Holdings Report'):
    response = client.post('/api/reports', headers=headers, json={
        'title': title, 'client_id': sample_client,
    })
    assert response.status_code == 201
    return response.get_json()

def test_create_report_starts_in_draft(client, auth_headers, sample_client):
    report = _create_report(client, auth_headers, sample_client)
    assert report['status'] == 'draft'
    assert report['file_path'].endswith('.pdf')

def test_happy_path_draft_to_distributed(client, auth_headers, sample_client):
    report = _create_report(client, auth_headers, sample_client)
    report_id = report['id']

    submitted = client.post(f'/api/reports/{report_id}/submit', headers=auth_headers)
    assert submitted.status_code == 200
    assert submitted.get_json()['status'] == 'review'

    approved = client.post(f'/api/reports/{report_id}/approve', headers=auth_headers)
    assert approved.status_code == 200
    assert approved.get_json()['status'] == 'approved'

    distributed = client.post(f'/api/reports/{report_id}/distribute', headers=auth_headers)
    assert distributed.status_code == 200
    assert distributed.get_json()['status'] == 'distributed'

    history = client.get(f'/api/reports/{report_id}/history', headers=auth_headers)
    assert history.status_code == 200
    transitions = [(t['from_status'], t['to_status']) for t in history.get_json()]
    assert transitions == [('draft', 'review'), ('review', 'approved'), ('approved', 'distributed')]

def test_reject_returns_to_draft(client, auth_headers, sample_client):
    report = _create_report(client, auth_headers, sample_client)
    report_id = report['id']
    client.post(f'/api/reports/{report_id}/submit', headers=auth_headers)

    rejected = client.post(f'/api/reports/{report_id}/reject', headers=auth_headers, json={'note': 'Fix figures'})
    assert rejected.status_code == 200
    assert rejected.get_json()['status'] == 'draft'

def test_invalid_transition_rejected(client, auth_headers, sample_client):
    report = _create_report(client, auth_headers, sample_client)
    response = client.post(f'/api/reports/{report["id"]}/distribute', headers=auth_headers)
    assert response.status_code == 409

def test_viewer_cannot_submit_or_approve(client, auth_headers, viewer_headers, sample_client):
    report = _create_report(client, auth_headers, sample_client)
    report_id = report['id']

    assert client.post(f'/api/reports/{report_id}/submit', headers=viewer_headers).status_code == 403

    client.post(f'/api/reports/{report_id}/submit', headers=auth_headers)
    assert client.post(f'/api/reports/{report_id}/approve', headers=viewer_headers).status_code == 403

def test_client_scoped_to_own_reports(client, auth_headers, client_portal_headers,
                                       other_client_portal_headers, sample_client):
    report = _create_report(client, auth_headers, sample_client)
    report_id = report['id']
    client.post(f'/api/reports/{report_id}/submit', headers=auth_headers)
    client.post(f'/api/reports/{report_id}/approve', headers=auth_headers)
    client.post(f'/api/reports/{report_id}/distribute', headers=auth_headers)

    forbidden = client.get(f'/api/reports/{report_id}', headers=other_client_portal_headers)
    assert forbidden.status_code == 404

    other_list = client.get('/api/reports', headers=other_client_portal_headers)
    assert other_list.get_json() == []

    own = client.get(f'/api/reports/{report_id}', headers=client_portal_headers)
    assert own.status_code == 200
    assert own.get_json()['id'] == report_id

def test_client_only_sees_distributed(client, auth_headers, client_portal_headers, sample_client):
    report = _create_report(client, auth_headers, sample_client)
    report_id = report['id']

    assert client.get(f'/api/reports/{report_id}', headers=client_portal_headers).status_code == 404
    assert client.get('/api/reports', headers=client_portal_headers).get_json() == []

    client.post(f'/api/reports/{report_id}/submit', headers=auth_headers)
    client.post(f'/api/reports/{report_id}/approve', headers=auth_headers)
    client.post(f'/api/reports/{report_id}/distribute', headers=auth_headers)

    visible = client.get(f'/api/reports/{report_id}', headers=client_portal_headers)
    assert visible.status_code == 200
