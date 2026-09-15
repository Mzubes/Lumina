from database import db_session
from models import WorkflowGroup

def _reviewable_components(group_id):
    return [
        {"id": "c1", "type": "text_block", "title": "Disclosures", "review_group_id": group_id,
         "data_binding": {"static_text": "All investments involve risk."}},
    ]

PLAIN_COMPONENTS = [
    {"id": "c1", "type": "text_block", "title": "Commentary",
     "data_binding": {"static_text": "No review tag here."}},
]

def _compliance_group_id(app, compliance_headers):
    # compliance_headers (tests/conftest.py) creates the "Compliance"
    # WorkflowGroup as a side effect of seeding its editor+group-member user.
    with app.app_context():
        return db_session.query(WorkflowGroup).filter_by(name='Compliance').first().id

def _create_template(client, editor_headers, components=PLAIN_COMPONENTS):
    return client.post('/api/templates', headers=editor_headers, json={
        'name': 'Activity Template', 'components': components,
    }).get_json()

def _create_templated_report(client, auth_headers, sample_client, template_id, report_type=None):
    payload = {'title': 'Activity Report', 'client_id': sample_client, 'template_id': template_id}
    if report_type:
        payload['report_type'] = report_type
    return client.post('/api/reports', headers=auth_headers, json=payload).get_json()

def test_activity_requires_staff_role(client, viewer_headers, client_portal_headers):
    assert client.get('/api/activity', headers=viewer_headers).status_code == 200
    assert client.get('/api/activity', headers=client_portal_headers).status_code == 403

def test_activity_includes_transition_events(client, editor_headers, auth_headers, sample_client):
    template = _create_template(client, editor_headers)
    report = _create_templated_report(client, auth_headers, sample_client, template['id'])
    client.post(f"/api/reports/{report['id']}/submit", headers=auth_headers)

    body = client.get('/api/activity', headers=auth_headers).get_json()
    transitions = [e for e in body if e['type'] == 'transition' and e['report_id'] == report['id']]
    assert len(transitions) == 1
    assert transitions[0]['summary'] == 'draft → review'
    assert transitions[0]['actor_email'] == 'admin@example.com'
    assert transitions[0]['report_title'] == 'Activity Report'

def test_activity_includes_component_review_events(client, editor_headers, auth_headers, compliance_headers, app, sample_client):
    group_id = _compliance_group_id(app, compliance_headers)
    template = _create_template(client, editor_headers, components=_reviewable_components(group_id))
    report = _create_templated_report(client, auth_headers, sample_client, template['id'], report_type='factsheet')
    client.post(f"/api/reports/{report['id']}/submit", headers=auth_headers)
    client.post(f"/api/reports/{report['id']}/approve", headers=auth_headers)
    client.post(f"/api/reports/{report['id']}/components/c1/review", headers=compliance_headers)

    body = client.get('/api/activity', headers=auth_headers).get_json()
    reviews = [e for e in body if e['type'] == 'component_review' and e['report_id'] == report['id']]
    assert len(reviews) == 1
    assert reviews[0]['summary'] == 'Reviewed "Disclosures"'
    assert reviews[0]['actor_email'] == 'compliance@example.com'

def test_activity_includes_distribution_link_events(client, editor_headers, auth_headers, compliance_headers, sample_client):
    template = _create_template(client, editor_headers, components=PLAIN_COMPONENTS)
    report = _create_templated_report(client, auth_headers, sample_client, template['id'])
    client.post(f"/api/reports/{report['id']}/submit", headers=auth_headers)
    client.post(f"/api/reports/{report['id']}/approve", headers=auth_headers)
    client.post(f"/api/reports/{report['id']}/distribute", headers=auth_headers)
    client.post(f"/api/reports/{report['id']}/distribution-links", headers=auth_headers, json={})

    body = client.get('/api/activity', headers=auth_headers).get_json()
    links = [e for e in body if e['type'] == 'distribution_link' and e['report_id'] == report['id']]
    assert len(links) == 1
    assert links[0]['summary'] == 'Created an anonymous distribution link'

def test_activity_sorted_newest_first_and_respects_limit(client, editor_headers, auth_headers, sample_client):
    template = _create_template(client, editor_headers, components=PLAIN_COMPONENTS)
    report = _create_templated_report(client, auth_headers, sample_client, template['id'])
    client.post(f"/api/reports/{report['id']}/submit", headers=auth_headers)
    client.post(f"/api/reports/{report['id']}/approve", headers=auth_headers)

    body = client.get('/api/activity', headers=auth_headers).get_json()
    timestamps = [e['created_at'] for e in body]
    assert timestamps == sorted(timestamps, reverse=True)

    limited = client.get('/api/activity?limit=1', headers=auth_headers).get_json()
    assert len(limited) == 1
    assert limited[0] == body[0]
