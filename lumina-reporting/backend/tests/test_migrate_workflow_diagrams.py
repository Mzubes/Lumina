import json

from database import db_session
from migrate_workflow_diagrams import migrate_workflow_diagrams
from models import (
    Report, ReportStepInstance, ReportTemplate, User, WorkflowDiagram, WorkflowGroup, WorkflowGroupMembership,
)

COMPONENTS = [{"id": "c1", "type": "text_block", "title": "Body", "data_binding": {"static_text": "x"}}]
COMPLIANCE_COMPONENTS = [
    {"id": "c1", "type": "text_block", "title": "Body", "data_binding": {"static_text": "x"},
     "review_role": "compliance"},
]

def _make_template(components=COMPONENTS, name='T'):
    template = ReportTemplate(name=name, components=json.dumps(components), created_by=1)
    db_session.add(template)
    db_session.commit()
    return template

def _make_report(template_id, sample_client, status='draft', report_type=None):
    report = Report(
        title='R', client_id=sample_client, template_id=template_id, status=status,
        report_type=report_type, created_by=1,
    )
    db_session.add(report)
    db_session.commit()
    return report

def test_migrates_compliance_users_to_group_and_editor_role(app):
    # role='compliance' can no longer be created through the app (VALID_ROLES
    # / the CLI's --role choices reject it) -- this simulates a pre-existing
    # deployment's data from before that vocabulary change, inserted
    # directly rather than through a fixture that (correctly) can't produce
    # it anymore.
    with app.app_context():
        user = User(email='legacy-compliance@example.com', role='compliance')
        user.set_password('legacy-password')
        db_session.add(user)
        db_session.commit()

        migrate_workflow_diagrams()

        db_session.expire_all()
        user = db_session.query(User).filter_by(email='legacy-compliance@example.com').first()
        assert user.role == 'editor'
        group = db_session.query(WorkflowGroup).filter_by(name='Compliance').first()
        assert group is not None
        assert db_session.query(WorkflowGroupMembership).filter_by(user_id=user.id, group_id=group.id).first()

def test_rewrites_compliance_review_role_components(app):
    with app.app_context():
        template = _make_template(components=COMPLIANCE_COMPONENTS)
        migrate_workflow_diagrams()
        db_session.expire_all()
        template = db_session.query(ReportTemplate).filter_by(id=template.id).first()
        components = template.components_list()
        assert 'review_role' not in components[0]
        group = db_session.query(WorkflowGroup).filter_by(name='Compliance').first()
        assert components[0]['review_group_id'] == group.id

def test_template_with_only_compliance_required_reports_gets_five_node_diagram(app, sample_client):
    with app.app_context():
        template = _make_template()
        _make_report(template.id, sample_client, report_type='factsheet')

        migrate_workflow_diagrams()

        diagram = db_session.query(WorkflowDiagram).filter_by(template_id=template.id, is_active=True).first()
        node_ids = {n['id'] for n in diagram.nodes_list()}
        assert 'compliance' in node_ids

def test_template_with_only_exempt_reports_gets_four_node_diagram(app, sample_client):
    with app.app_context():
        template = _make_template()
        _make_report(template.id, sample_client, report_type='performance')

        migrate_workflow_diagrams()

        diagram = db_session.query(WorkflowDiagram).filter_by(template_id=template.id, is_active=True).first()
        node_ids = {n['id'] for n in diagram.nodes_list()}
        assert 'compliance' not in node_ids

def test_template_with_mixed_report_types_gets_safe_with_compliance_variant(app, sample_client):
    with app.app_context():
        template = _make_template()
        _make_report(template.id, sample_client, report_type='factsheet')
        _make_report(template.id, sample_client, report_type='performance')

        migrate_workflow_diagrams()

        diagram = db_session.query(WorkflowDiagram).filter_by(template_id=template.id, is_active=True).first()
        node_ids = {n['id'] for n in diagram.nodes_list()}
        assert 'compliance' in node_ids

def test_template_with_no_reports_defaults_to_with_compliance(app):
    with app.app_context():
        template = _make_template()
        migrate_workflow_diagrams()
        diagram = db_session.query(WorkflowDiagram).filter_by(template_id=template.id, is_active=True).first()
        assert 'compliance' in {n['id'] for n in diagram.nodes_list()}

def test_backfills_in_flight_report_to_matching_node(app, sample_client):
    with app.app_context():
        template = _make_template()
        report = _make_report(template.id, sample_client, status='review', report_type='factsheet')

        migrate_workflow_diagrams()

        db_session.expire_all()
        report = db_session.query(Report).filter_by(id=report.id).first()
        assert report.workflow_diagram_id is not None
        instances = db_session.query(ReportStepInstance).filter_by(report_id=report.id, state='active').all()
        assert [i.node_id for i in instances] == ['review']

def test_skips_template_that_already_has_an_active_diagram(app, sample_client):
    with app.app_context():
        template = _make_template()
        hand_authored = WorkflowDiagram(
            template_id=template.id, version=1, is_active=True,
            nodes=json.dumps([{'id': 'x', 'name': 'X', 'type': 'start', 'group_id': None, 'position': {'x': 0, 'y': 0}}]),
            edges=json.dumps([]), generated=False, created_by=1,
        )
        db_session.add(hand_authored)
        db_session.commit()

        migrate_workflow_diagrams()

        diagrams = db_session.query(WorkflowDiagram).filter_by(template_id=template.id).all()
        assert len(diagrams) == 1
        assert diagrams[0].id == hand_authored.id

def test_dry_run_does_not_commit(app, sample_client):
    with app.app_context():
        template = _make_template()
        migrate_workflow_diagrams(dry_run=True)
        db_session.expire_all()
        assert db_session.query(WorkflowDiagram).filter_by(template_id=template.id).first() is None

def test_is_idempotent(app, sample_client):
    with app.app_context():
        template = _make_template()
        migrate_workflow_diagrams()
        migrate_workflow_diagrams()
        diagrams = db_session.query(WorkflowDiagram).filter_by(template_id=template.id).all()
        assert len(diagrams) == 1

def _fire(client, headers, report_id, label):
    """Fires a diagram-backed report's action by its edge label -- the same
    lookup the real frontend does (getReportActions reads eligibleActions,
    fireReportAction posts the matching edge_id to /transition). The six
    legacy verb routes are the legacy (non-diagram) engine's interface only
    now, so a diagram-backed report (like the one this test builds) is
    driven through /transition directly."""
    actions = client.get(f'/api/reports/{report_id}/eligible-actions', headers=headers).get_json()
    match = next(a for a in actions if a['label'] == label)
    return client.post(f'/api/reports/{report_id}/transition', headers=headers, json={'edge_id': match['edge_id']})

def test_generated_diagram_reproduces_legacy_behavior_via_transition_endpoint(client, auth_headers, editor_headers, sample_client):
    template = client.post('/api/templates', headers=editor_headers, json={
        'name': 'Factsheet Template', 'components': COMPONENTS,
    }).get_json()
    report = client.post('/api/reports', headers=auth_headers, json={
        'title': 'R', 'client_id': sample_client, 'template_id': template['id'], 'report_type': 'factsheet',
    }).get_json()

    migrate_workflow_diagrams()

    report_id = report['id']
    assert _fire(client, auth_headers, report_id, 'Submit').status_code == 200
    approved = _fire(client, auth_headers, report_id, 'Approve')
    assert approved.status_code == 200
    assert approved.get_json()['status'] == 'Compliance'

    certified = _fire(client, auth_headers, report_id, 'Certify')
    assert certified.status_code == 200
    assert certified.get_json()['status'] == 'Approved'

    distributed = _fire(client, auth_headers, report_id, 'Distribute')
    assert distributed.status_code == 200
    assert distributed.get_json()['status'] == 'Distributed'
