import json

import pytest

from database import db_session
from models import Report, User, WorkflowDiagram, WorkflowGroup, WorkflowGroupMembership
from workflow_engine import (
    InvalidTransition,
    NotAuthorized,
    active_instances,
    apply_transition,
    eligible_actions,
    start_report,
)

ADMIN_ID = 1  # seeded by the `app` fixture in conftest.py

def _node(node_id, name, node_type='step', group_id=None, is_terminal=False):
    return {
        'id': node_id, 'name': name, 'type': node_type, 'group_id': group_id,
        'position': {'x': 0, 'y': 0}, 'is_distribution_gate': False, 'is_terminal': is_terminal,
    }

def _edge(edge_id, from_node, to_node, label='Next'):
    return {'id': edge_id, 'from_node': from_node, 'to_node': to_node, 'action_label': label}

def _build(app, sample_client, sample_template, nodes, edges, workflow_diagram_id='set'):
    """Creates a WorkflowDiagram from hand-built node/edge lists and a Report
    pinned to it (unless workflow_diagram_id=None, for the no-diagram case).
    Returns (report_id, diagram_id)."""
    with app.app_context():
        diagram = WorkflowDiagram(
            template_id=sample_template, version=1, is_active=True,
            nodes=json.dumps(nodes), edges=json.dumps(edges), generated=False, created_by=ADMIN_ID,
        )
        db_session.add(diagram)
        db_session.commit()
        report = Report(
            title='Engine Test Report', client_id=sample_client, template_id=sample_template,
            created_by=ADMIN_ID, workflow_diagram_id=(diagram.id if workflow_diagram_id == 'set' else None),
        )
        db_session.add(report)
        db_session.commit()
        return report.id, diagram.id

def _make_user(email, role='editor'):
    user = User(email=email, role=role)
    user.set_password('password123')
    db_session.add(user)
    db_session.commit()
    return user

# ---------- linear traversal ----------

LINEAR_NODES = [
    _node('start', 'Start', 'start'),
    _node('draft', 'Draft'),
    _node('review', 'Review'),
    _node('done', 'Distributed', 'terminal', is_terminal=True),
]
LINEAR_EDGES = [
    _edge('e-start', 'start', 'draft'),
    _edge('e-submit', 'draft', 'review', 'Submit'),
    _edge('e-finish', 'review', 'done', 'Distribute'),
]

def test_linear_traversal(app, sample_client, sample_template):
    report_id, diagram_id = _build(app, sample_client, sample_template, LINEAR_NODES, LINEAR_EDGES)
    with app.app_context():
        report = db_session.query(Report).get(report_id)
        diagram = db_session.query(WorkflowDiagram).get(diagram_id)

        start_report(report, diagram, ADMIN_ID)
        assert [i.node_id for i in active_instances(report)] == ['draft']
        assert report.status == 'Draft'

        apply_transition(report, 'e-submit', ADMIN_ID)
        assert [i.node_id for i in active_instances(report)] == ['review']
        assert report.status == 'Review'

        apply_transition(report, 'e-finish', ADMIN_ID)
        assert [i.node_id for i in active_instances(report)] == ['done']
        assert report.status == 'Distributed'

def test_linear_transition_dual_writes_report_transition(app, sample_client, sample_template):
    report_id, diagram_id = _build(app, sample_client, sample_template, LINEAR_NODES, LINEAR_EDGES)
    with app.app_context():
        report = db_session.query(Report).get(report_id)
        diagram = db_session.query(WorkflowDiagram).get(diagram_id)
        start_report(report, diagram, ADMIN_ID)
        apply_transition(report, 'e-submit', ADMIN_ID, note='looks good')

        from models import ReportTransition
        transitions = db_session.query(ReportTransition).filter_by(report_id=report_id).order_by(ReportTransition.id).all()
        assert [t.to_status for t in transitions] == ['Draft', 'Review']
        assert transitions[-1].note == 'looks good'
        assert transitions[-1].actor_id == ADMIN_ID

# ---------- parallel fan-out + AND-join ----------

PARALLEL_NODES = [
    _node('start', 'Start', 'start'),
    _node('gateway', 'Split', 'parallel_gateway'),
    _node('branch-a', 'Compliance Review', group_id=None),
    _node('branch-b', 'PM Review', group_id=None),
    _node('join', 'Join', 'join'),
    _node('done', 'Distributed', 'terminal', is_terminal=True),
]
PARALLEL_EDGES = [
    _edge('e-start', 'start', 'gateway'),
    _edge('e-fan-a', 'gateway', 'branch-a'),
    _edge('e-fan-b', 'gateway', 'branch-b'),
    _edge('e-a-done', 'branch-a', 'join', 'A Done'),
    _edge('e-b-done', 'branch-b', 'join', 'B Done'),
    _edge('e-finish', 'join', 'done', 'Distribute'),
]

def test_parallel_fan_out_creates_multiple_active_instances(app, sample_client, sample_template):
    report_id, diagram_id = _build(app, sample_client, sample_template, PARALLEL_NODES, PARALLEL_EDGES)
    with app.app_context():
        report = db_session.query(Report).get(report_id)
        diagram = db_session.query(WorkflowDiagram).get(diagram_id)
        start_report(report, diagram, ADMIN_ID)

        actives = {i.node_id for i in active_instances(report)}
        assert actives == {'branch-a', 'branch-b'}
        assert report.status == '2 steps in progress'

def test_and_join_does_not_fire_on_partial_completion(app, sample_client, sample_template):
    report_id, diagram_id = _build(app, sample_client, sample_template, PARALLEL_NODES, PARALLEL_EDGES)
    with app.app_context():
        report = db_session.query(Report).get(report_id)
        diagram = db_session.query(WorkflowDiagram).get(diagram_id)
        start_report(report, diagram, ADMIN_ID)

        apply_transition(report, 'e-a-done', ADMIN_ID)
        actives = {i.node_id for i in active_instances(report)}
        # Only branch-b still active -- the join must NOT have fired yet.
        assert actives == {'branch-b'}
        assert report.status == 'PM Review'
        assert eligible_actions(report, 'admin', ADMIN_ID) == [
            {'edge_id': 'e-b-done', 'label': 'B Done', 'node_id': 'branch-b'},
        ]

def test_and_join_fires_once_all_branches_done(app, sample_client, sample_template):
    report_id, diagram_id = _build(app, sample_client, sample_template, PARALLEL_NODES, PARALLEL_EDGES)
    with app.app_context():
        report = db_session.query(Report).get(report_id)
        diagram = db_session.query(WorkflowDiagram).get(diagram_id)
        start_report(report, diagram, ADMIN_ID)

        apply_transition(report, 'e-a-done', ADMIN_ID)
        apply_transition(report, 'e-b-done', ADMIN_ID)

        actives = {i.node_id for i in active_instances(report)}
        assert actives == {'join'}
        assert report.status == 'Join'

        apply_transition(report, 'e-finish', ADMIN_ID)
        assert {i.node_id for i in active_instances(report)} == {'done'}
        assert report.status == 'Distributed'

# ---------- eligibility: generic, group-restricted, admin override ----------

GENERIC_NODES = [
    _node('start', 'Start', 'start'),
    _node('step', 'Do The Thing', group_id=None),
    _node('done', 'Done', 'terminal', is_terminal=True),
]
GENERIC_EDGES = [
    _edge('e-start', 'start', 'step'),
    _edge('e-finish', 'step', 'done', 'Finish'),
]

def test_generic_node_any_editor_or_admin_can_act_but_not_viewer(app, sample_client, sample_template):
    report_id, diagram_id = _build(app, sample_client, sample_template, GENERIC_NODES, GENERIC_EDGES)
    with app.app_context():
        editor = _make_user('engine-editor@example.com', role='editor')
        viewer = _make_user('engine-viewer@example.com', role='viewer')
        report = db_session.query(Report).get(report_id)
        diagram = db_session.query(WorkflowDiagram).get(diagram_id)
        start_report(report, diagram, ADMIN_ID)

        assert eligible_actions(report, 'viewer', viewer.id) == []
        assert eligible_actions(report, 'editor', editor.id) == [
            {'edge_id': 'e-finish', 'label': 'Finish', 'node_id': 'step'},
        ]

        with pytest.raises(NotAuthorized):
            apply_transition(report, 'e-finish', viewer.id)

        # An editor with no group membership at all can still act -- the
        # node is generic (group_id=None).
        apply_transition(report, 'e-finish', editor.id)
        assert {i.node_id for i in active_instances(report)} == {'done'}

def _group_restricted_diagram():
    nodes = [
        _node('start', 'Start', 'start'),
        _node('step', 'Compliance Sign-off', group_id='__GROUP_ID__'),
        _node('done', 'Done', 'terminal', is_terminal=True),
    ]
    edges = [
        _edge('e-start', 'start', 'step'),
        _edge('e-finish', 'step', 'done', 'Sign Off'),
    ]
    return nodes, edges

def test_group_restricted_node_requires_membership(app, sample_client, sample_template):
    with app.app_context():
        group = WorkflowGroup(name='Compliance', created_by=ADMIN_ID)
        db_session.add(group)
        db_session.commit()
        group_id = group.id

        member = _make_user('engine-member@example.com', role='editor')
        db_session.add(WorkflowGroupMembership(user_id=member.id, group_id=group_id))
        non_member = _make_user('engine-nonmember@example.com', role='editor')
        db_session.commit()

    nodes, edges = _group_restricted_diagram()
    nodes[1]['group_id'] = group_id
    report_id, diagram_id = _build(app, sample_client, sample_template, nodes, edges)

    with app.app_context():
        report = db_session.query(Report).get(report_id)
        diagram = db_session.query(WorkflowDiagram).get(diagram_id)
        start_report(report, diagram, ADMIN_ID)

        member = db_session.query(User).filter_by(email='engine-member@example.com').first()
        non_member = db_session.query(User).filter_by(email='engine-nonmember@example.com').first()

        assert eligible_actions(report, 'editor', non_member.id) == []
        assert eligible_actions(report, 'editor', member.id) == [
            {'edge_id': 'e-finish', 'label': 'Sign Off', 'node_id': 'step'},
        ]

        with pytest.raises(NotAuthorized):
            apply_transition(report, 'e-finish', non_member.id)

        # Admin overrides group membership entirely.
        apply_transition(report, 'e-finish', ADMIN_ID)
        assert {i.node_id for i in active_instances(report)} == {'done'}

# ---------- invalid input handling ----------

def test_apply_transition_unknown_edge_raises(app, sample_client, sample_template):
    report_id, diagram_id = _build(app, sample_client, sample_template, GENERIC_NODES, GENERIC_EDGES)
    with app.app_context():
        report = db_session.query(Report).get(report_id)
        diagram = db_session.query(WorkflowDiagram).get(diagram_id)
        start_report(report, diagram, ADMIN_ID)

        with pytest.raises(InvalidTransition):
            apply_transition(report, 'no-such-edge', ADMIN_ID)

def test_apply_transition_on_inactive_node_raises(app, sample_client, sample_template):
    report_id, diagram_id = _build(app, sample_client, sample_template, GENERIC_NODES, GENERIC_EDGES)
    with app.app_context():
        report = db_session.query(Report).get(report_id)
        diagram = db_session.query(WorkflowDiagram).get(diagram_id)
        start_report(report, diagram, ADMIN_ID)
        apply_transition(report, 'e-finish', ADMIN_ID)  # now at 'done'

        with pytest.raises(InvalidTransition):
            # 'e-finish' fires from 'step', which is no longer active.
            apply_transition(report, 'e-finish', ADMIN_ID)

def test_report_without_diagram_has_no_eligible_actions(app, sample_client, sample_template):
    report_id, _ = _build(app, sample_client, sample_template, GENERIC_NODES, GENERIC_EDGES, workflow_diagram_id=None)
    with app.app_context():
        report = db_session.query(Report).get(report_id)
        assert eligible_actions(report, 'admin', ADMIN_ID) == []

        with pytest.raises(InvalidTransition):
            apply_transition(report, 'e-finish', ADMIN_ID)
