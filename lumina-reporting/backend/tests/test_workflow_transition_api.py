import json

from database import db_session
from models import Report, WorkflowDiagram
from workflow_engine import start_report

def _node(node_id, name, node_type='step', group_id=None, is_terminal=False, is_distribution_gate=False):
    return {
        'id': node_id, 'name': name, 'type': node_type, 'group_id': group_id,
        'position': {'x': 0, 'y': 0}, 'is_distribution_gate': is_distribution_gate, 'is_terminal': is_terminal,
    }

def _edge(edge_id, from_node, to_node, label='Next'):
    return {'id': edge_id, 'from_node': from_node, 'to_node': to_node, 'action_label': label}

# A tiny two-step diagram whose terminal node is deliberately NOT named
# "distributed" -- proving the distribution gate is genuinely node-flag-based
# now, not a disguised string comparison.
NODES = [
    _node('start', 'Start', 'start'),
    _node('draft', 'Draft'),
    _node('published', 'Published', 'terminal', is_terminal=True, is_distribution_gate=True),
]
EDGES = [
    _edge('e-start', 'start', 'draft'),
    _edge('e-submit', 'draft', 'published', 'Submit'),
]

def _create_report(client, auth_headers, sample_client):
    response = client.post('/api/reports', headers=auth_headers, json={'title': 'Diagram Report', 'client_id': sample_client})
    assert response.status_code == 201
    return response.get_json()['id']

def _attach_diagram(app, sample_template, report_id, nodes=NODES, edges=EDGES):
    with app.app_context():
        diagram = WorkflowDiagram(
            template_id=sample_template, version=1, is_active=True,
            nodes=json.dumps(nodes), edges=json.dumps(edges), generated=False, created_by=1,
        )
        db_session.add(diagram)
        db_session.commit()
        report = db_session.query(Report).get(report_id)
        report.workflow_diagram_id = diagram.id
        db_session.commit()
        start_report(report, diagram, 1)
        return diagram.id

def test_eligible_actions_empty_for_legacy_report(client, auth_headers, sample_client):
    report_id = _create_report(client, auth_headers, sample_client)
    response = client.get(f'/api/reports/{report_id}/eligible-actions', headers=auth_headers)
    assert response.status_code == 200
    assert response.get_json() == []

def test_eligible_actions_and_transition_for_diagram_backed_report(app, client, auth_headers, sample_client, sample_template):
    report_id = _create_report(client, auth_headers, sample_client)
    _attach_diagram(app, sample_template, report_id)

    actions = client.get(f'/api/reports/{report_id}/eligible-actions', headers=auth_headers).get_json()
    assert actions == [{'edge_id': 'e-submit', 'label': 'Submit', 'node_id': 'draft'}]

    response = client.post(f'/api/reports/{report_id}/transition', headers=auth_headers, json={'edge_id': 'e-submit'})
    assert response.status_code == 200
    body = response.get_json()
    assert body['status'] == 'Published'
    assert body['activeSteps'][0]['node_id'] == 'published'

def test_transition_rejects_unknown_edge(app, client, auth_headers, sample_client, sample_template):
    report_id = _create_report(client, auth_headers, sample_client)
    _attach_diagram(app, sample_template, report_id)
    response = client.post(f'/api/reports/{report_id}/transition', headers=auth_headers, json={'edge_id': 'nope'})
    assert response.status_code == 409

def test_transition_requires_edge_id(app, client, auth_headers, sample_client, sample_template):
    report_id = _create_report(client, auth_headers, sample_client)
    _attach_diagram(app, sample_template, report_id)
    response = client.post(f'/api/reports/{report_id}/transition', headers=auth_headers, json={})
    assert response.status_code == 400

def test_client_role_forbidden_from_transition_endpoints(client, client_portal_headers, sample_client):
    with_client = client.get('/api/reports/1/eligible-actions', headers=client_portal_headers)
    assert with_client.status_code == 403
    with_client = client.post('/api/reports/1/transition', headers=client_portal_headers, json={'edge_id': 'x'})
    assert with_client.status_code == 403

def test_legacy_submit_verb_resolves_through_new_engine_for_diagram_backed_report(
    app, client, auth_headers, sample_client, sample_template,
):
    report_id = _create_report(client, auth_headers, sample_client)
    _attach_diagram(app, sample_template, report_id)

    response = client.post(f'/api/reports/{report_id}/submit', headers=auth_headers)
    assert response.status_code == 200
    body = response.get_json()
    assert body['status'] == 'Published'

def test_legacy_submit_verb_409s_once_no_matching_edge_is_eligible(
    app, client, auth_headers, sample_client, sample_template,
):
    report_id = _create_report(client, auth_headers, sample_client)
    _attach_diagram(app, sample_template, report_id)
    client.post(f'/api/reports/{report_id}/submit', headers=auth_headers)  # now at 'published', a terminal node

    response = client.post(f'/api/reports/{report_id}/submit', headers=auth_headers)
    assert response.status_code == 409

def test_distribution_gate_is_node_flag_based_not_string_based(
    app, client, auth_headers, sample_client, sample_template,
):
    """The diagram's terminal node is named 'Published', not 'distributed' --
    proving create_distribution_link and client-portal visibility now key off
    is_distribution_gate rather than the literal string 'distributed'."""
    report_id = _create_report(client, auth_headers, sample_client)
    _attach_diagram(app, sample_template, report_id)

    denied = client.post(f'/api/reports/{report_id}/distribution-links', headers=auth_headers, json={})
    assert denied.status_code == 409

    client.post(f'/api/reports/{report_id}/submit', headers=auth_headers)

    allowed = client.post(f'/api/reports/{report_id}/distribution-links', headers=auth_headers, json={})
    assert allowed.status_code == 201
