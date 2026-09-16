from migrate_workflow_diagrams import migrate_workflow_diagrams

def _create_report(client, headers, sample_client, **overrides):
    payload = {'title': 'Untitled Report', 'client_id': sample_client}
    payload.update(overrides)
    response = client.post('/api/reports', headers=headers, json=payload)
    assert response.status_code == 201
    return response.get_json()

PLAIN_COMPONENTS = [{"id": "c1", "type": "text_block", "title": "Body", "data_binding": {"static_text": "x"}}]

def _create_migrated_report(client, editor_headers, auth_headers, app, sample_client, report_type):
    """Creates a templated report pinned to an auto-generated workflow
    diagram (via the real migration command, same as production rollout).
    A brand-new template has no report history yet, so its generated
    diagram always takes the safe (with-compliance) variant regardless of
    report_type -- this helper is only used by tests that need a
    compliance-required report_type for that reason; the report_type-
    dependent skip-compliance tests below deliberately stay on the pure
    legacy (template-less) path, since a single per-template diagram can't
    replicate that per-report dynamic branching (see
    migrate_workflow_diagrams.py's module docstring)."""
    template = client.post('/api/templates', headers=editor_headers, json={
        'name': 'Compliance Shim Template', 'components': PLAIN_COMPONENTS,
    }).get_json()
    with app.app_context():
        migrate_workflow_diagrams()
    return _create_report(
        client, auth_headers, sample_client, report_type=report_type, template_id=template['id'],
    )

def _fire(client, headers, report_id, label, note=None):
    """Fires a diagram-backed report's action by its edge label, the same
    two-step lookup the real frontend does now (getReportActions in
    ReportsTable.js reads eligibleActions, fireReportAction in api.js posts
    the matching edge_id to /transition) -- the six legacy verb routes are
    legacy-engine-only now and no longer resolve a diagram edge on a
    caller's behalf (see routes/reports.py's _transition_route)."""
    actions = client.get(f'/api/reports/{report_id}/eligible-actions', headers=headers).get_json()
    match = next(a for a in actions if a['label'] == label)
    body = {'edge_id': match['edge_id']}
    if note is not None:
        body['note'] = note
    return client.post(f'/api/reports/{report_id}/transition', headers=headers, json=body)

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

def test_certify_moves_to_approved(client, editor_headers, auth_headers, compliance_headers, app, sample_client):
    report = _create_migrated_report(client, editor_headers, auth_headers, app, sample_client, report_type='pitchbook')
    report_id = report['id']
    _fire(client, auth_headers, report_id, 'Submit')
    _fire(client, auth_headers, report_id, 'Approve')

    certified = _fire(client, compliance_headers, report_id, 'Certify')
    assert certified.status_code == 200
    assert certified.get_json()['status'] == 'Approved'

def test_request_changes_returns_to_draft(client, editor_headers, auth_headers, compliance_headers, app, sample_client):
    report = _create_migrated_report(client, editor_headers, auth_headers, app, sample_client, report_type='marketing')
    report_id = report['id']
    _fire(client, auth_headers, report_id, 'Submit')
    _fire(client, auth_headers, report_id, 'Approve')

    sent_back = _fire(client, compliance_headers, report_id, 'Request Changes', note='Fix the disclosures')
    assert sent_back.status_code == 200
    assert sent_back.get_json()['status'] == 'Draft'

    history = client.get(f'/api/reports/{report_id}/history', headers=auth_headers).get_json()
    assert history[-1]['from_status'] == 'Compliance'
    assert history[-1]['to_status'] == 'Draft'
    assert history[-1]['note'] == 'Fix the disclosures'

def test_compliance_group_member_can_certify_legacy_report(client, auth_headers, compliance_headers, sample_client):
    # Template-less report -- pin_to_active_diagram never fires (no
    # template_id to look a diagram up by), so this stays on the pure legacy
    # engine forever. role='compliance' can no longer be created, so the
    # legacy certify/request-changes branch must authorize via "Compliance"
    # WorkflowGroup membership instead (see _legacy_compliance_group_id in
    # routes/reports.py) -- this is the report-status-string half of that
    # fix; test_migrate_workflow_diagrams.py covers the group getting
    # created for a pre-existing role='compliance' user.
    report = _create_report(client, auth_headers, sample_client, report_type='pitchbook')
    report_id = report['id']
    client.post(f'/api/reports/{report_id}/submit', headers=auth_headers)
    approved = client.post(f'/api/reports/{report_id}/approve', headers=auth_headers)
    assert approved.get_json()['status'] == 'compliance'

    certified = client.post(f'/api/reports/{report_id}/certify', headers=compliance_headers)
    assert certified.status_code == 200
    assert certified.get_json()['status'] == 'approved'

def test_admin_cannot_certify(client, auth_headers, sample_client):
    report = _create_report(client, auth_headers, sample_client, report_type='pitchbook')
    report_id = report['id']
    client.post(f'/api/reports/{report_id}/submit', headers=auth_headers)
    client.post(f'/api/reports/{report_id}/approve', headers=auth_headers)

    response = client.post(f'/api/reports/{report_id}/certify', headers=auth_headers)
    assert response.status_code == 403

def test_compliance_cannot_certify_from_review(client, editor_headers, auth_headers, compliance_headers, app, sample_client):
    report = _create_migrated_report(client, editor_headers, auth_headers, app, sample_client, report_type='pitchbook')
    report_id = report['id']
    _fire(client, auth_headers, report_id, 'Submit')

    diagram = client.get(f'/api/reports/{report_id}/workflow', headers=auth_headers).get_json()
    certify_edge = next(e for e in diagram['edges'] if e['action_label'] == 'Certify')

    # The report's active step is 'Review', not 'Compliance' -- no active
    # instance exists for the Certify edge's from_node yet, so the engine
    # rejects firing it outright, regardless of the actor's own eligibility.
    response = client.post(
        f'/api/reports/{report_id}/transition', headers=compliance_headers, json={'edge_id': certify_edge['id']},
    )
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

def test_full_happy_path_through_compliance(client, editor_headers, auth_headers, compliance_headers, app, sample_client):
    report = _create_migrated_report(client, editor_headers, auth_headers, app, sample_client, report_type='meeting_pack')
    report_id = report['id']

    assert _fire(client, auth_headers, report_id, 'Submit').get_json()['status'] == 'Review'
    assert _fire(client, auth_headers, report_id, 'Approve').get_json()['status'] == 'Compliance'
    assert _fire(client, compliance_headers, report_id, 'Certify').get_json()['status'] == 'Approved'
    assert _fire(client, auth_headers, report_id, 'Distribute').get_json()['status'] == 'Distributed'
