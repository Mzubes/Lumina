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

def test_every_activity_event_carries_a_unique_reference(client, editor_headers, auth_headers, sample_client):
    template = _create_template(client, editor_headers)
    report = _create_templated_report(client, auth_headers, sample_client, template['id'])
    client.post(f"/api/reports/{report['id']}/submit", headers=auth_headers)
    client.post(f"/api/reports/{report['id']}/approve", headers=auth_headers)
    client.post(f"/api/reports/{report['id']}/distribute", headers=auth_headers)
    client.post(f"/api/reports/{report['id']}/distribution-links", headers=auth_headers, json={})

    body = client.get('/api/activity', headers=auth_headers).get_json()
    references = [event['reference'] for event in body]

    assert all(reference.startswith('REF-') for reference in references)
    # Ids only count within their own table, so the per-source letter is what
    # keeps a transition and a distribution link from colliding on REF-1.
    assert len(set(references)) == len(references)

    prefixes = {event['type']: event['reference'][4] for event in body}
    assert prefixes['transition'] == 'T'
    assert prefixes['distribution_link'] == 'D'

def test_reference_is_stable_across_requests(client, editor_headers, auth_headers, sample_client):
    template = _create_template(client, editor_headers)
    report = _create_templated_report(client, auth_headers, sample_client, template['id'])
    client.post(f"/api/reports/{report['id']}/submit", headers=auth_headers)

    first = client.get('/api/activity', headers=auth_headers).get_json()
    second = client.get('/api/activity', headers=auth_headers).get_json()
    assert [e['reference'] for e in first] == [e['reference'] for e in second]


# ---------- Phase 4d: action types, target, filters, export ----------

from routes.activity import _transition_action_type


def test_action_type_reads_the_firms_own_step_names():
    # The vocabulary is derived from the words the firm used, so a renamed
    # workflow keeps meaningful categories with no migration.
    assert _transition_action_type(None, 'draft') == 'created'
    assert _transition_action_type('approved', 'Distributed') == 'distribution'
    assert _transition_action_type('review', 'Compliance review') == 'compliance'
    assert _transition_action_type('review', 'Risk sign-off') == 'compliance'
    assert _transition_action_type('compliance', 'Approved') == 'sign_off'
    assert _transition_action_type('review', 'Draft') == 'workflow'


def test_a_rejection_out_of_compliance_is_a_rejection_not_a_compliance_event():
    assert _transition_action_type('compliance', 'Sent back for revisions') == 'rejected'
    assert _transition_action_type('review', 'Rejected') == 'rejected'


def test_events_carry_an_action_type_and_a_target(client, auth_headers, sample_client):
    created = client.post('/api/reports', headers=auth_headers, json={'title': 'Q3', 'client_id': sample_client})
    report_id = created.get_json()['id']
    client.post(f'/api/reports/{report_id}/submit', headers=auth_headers)

    events = client.get('/api/activity', headers=auth_headers).get_json()
    assert events, 'expected at least the submit transition'
    for event in events:
        assert event['actionType']
        assert event['target']


def test_filter_by_report_id(client, auth_headers, sample_client):
    a = client.post('/api/reports', headers=auth_headers, json={'title': 'A', 'client_id': sample_client}).get_json()['id']
    b = client.post('/api/reports', headers=auth_headers, json={'title': 'B', 'client_id': sample_client}).get_json()['id']
    client.post(f'/api/reports/{a}/submit', headers=auth_headers)
    client.post(f'/api/reports/{b}/submit', headers=auth_headers)

    events = client.get(f'/api/activity?report_id={a}', headers=auth_headers).get_json()
    assert events and all(event['report_id'] == a for event in events)


def test_filter_by_actor_is_a_case_insensitive_substring(client, auth_headers, sample_client):
    report_id = client.post('/api/reports', headers=auth_headers, json={'title': 'A', 'client_id': sample_client}).get_json()['id']
    client.post(f'/api/reports/{report_id}/submit', headers=auth_headers)

    assert client.get('/api/activity?actor=ADMIN@', headers=auth_headers).get_json()
    assert client.get('/api/activity?actor=nobody@example.com', headers=auth_headers).get_json() == []


def test_filter_by_action_type(client, auth_headers, sample_client):
    report_id = client.post('/api/reports', headers=auth_headers, json={'title': 'A', 'client_id': sample_client}).get_json()['id']
    client.post(f'/api/reports/{report_id}/submit', headers=auth_headers)

    events = client.get('/api/activity?action_type=workflow', headers=auth_headers).get_json()
    assert all(event['actionType'] == 'workflow' for event in events)
    assert client.get('/api/activity?action_type=distribution', headers=auth_headers).get_json() == []


def test_until_covers_the_whole_named_day(client, auth_headers, sample_client):
    # A timestamp of 14:02 on the 20th must be included by until=2026-...-20,
    # not excluded because it's later than midnight.
    import datetime
    report_id = client.post('/api/reports', headers=auth_headers, json={'title': 'A', 'client_id': sample_client}).get_json()['id']
    client.post(f'/api/reports/{report_id}/submit', headers=auth_headers)

    today = datetime.datetime.utcnow().date().isoformat()
    assert client.get(f'/api/activity?until={today}', headers=auth_headers).get_json()
    yesterday = (datetime.datetime.utcnow().date() - datetime.timedelta(days=1)).isoformat()
    assert client.get(f'/api/activity?until={yesterday}', headers=auth_headers).get_json() == []


def test_export_returns_csv_of_exactly_what_the_filters_select(client, auth_headers, sample_client):
    a = client.post('/api/reports', headers=auth_headers, json={'title': 'Alpha', 'client_id': sample_client}).get_json()['id']
    b = client.post('/api/reports', headers=auth_headers, json={'title': 'Beta', 'client_id': sample_client}).get_json()['id']
    client.post(f'/api/reports/{a}/submit', headers=auth_headers)
    client.post(f'/api/reports/{b}/submit', headers=auth_headers)

    response = client.get(f'/api/activity/export?report_id={a}', headers=auth_headers)
    assert response.status_code == 200
    assert response.mimetype == 'text/csv'
    assert 'attachment; filename="lumina-audit-trail-' in response.headers['Content-Disposition']

    body = response.get_data(as_text=True)
    lines = [line for line in body.splitlines() if line.strip()]
    assert lines[0].startswith('Reference,Timestamp (UTC),Action,Actor,Report,Target,Detail')
    assert 'Alpha' in body and 'Beta' not in body
    # One header plus one row per selected event -- the export and the screen
    # go through the same _collect().
    assert len(lines) - 1 == len(client.get(f'/api/activity?report_id={a}', headers=auth_headers).get_json())


def test_export_requires_a_staff_role(client, client_portal_headers):
    assert client.get('/api/activity/export', headers=client_portal_headers).status_code == 403
