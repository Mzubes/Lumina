# Generic, per-template-diagram workflow engine -- replaces workflow_legacy's
# fixed five-status TRANSITIONS dict. A report is pinned to one
# WorkflowDiagram (report.workflow_diagram_id, set once at creation and never
# re-derived from "the template's current diagram", so editing a diagram
# never rewrites the graph under an in-flight report). Where the report
# currently sits is tracked by ReportStepInstance rows, not report.status --
# a report can have several simultaneously 'active' instances when its
# diagram has parallel branches, which a single status string can't
# represent. report.status is recomputed after every transition purely as a
# denormalized display label for consumers that just want a human-readable
# string (list views, filters).
import datetime
import json

from database import db_session
from models import ReportStepInstance, ReportTransition, User, WorkflowDiagram, WorkflowGroupMembership

class InvalidTransition(Exception):
    pass

class NotAuthorized(Exception):
    pass

# Structural node types auto-complete the instant they're entered and fan
# out to every outgoing edge's target -- they're never something a user
# takes an action on. 'start' always has exactly one outgoing edge (diagram
# validation enforces this at save time); 'parallel_gateway' may have several,
# which is what actually starts a parallel branch.
_STRUCTURAL_NODE_TYPES = ('start', 'parallel_gateway')

def _index(diagram):
    nodes_by_id = {n['id']: n for n in diagram.nodes_list()}
    edges_by_id = {e['id']: e for e in diagram.edges_list()}
    return nodes_by_id, edges_by_id

def _outgoing_edges(edges_by_id, node_id):
    return [e for e in edges_by_id.values() if e['from_node'] == node_id]

def _edges_into(edges_by_id, node_id):
    return [e for e in edges_by_id.values() if e['to_node'] == node_id]

def _group_ids_for(user_id):
    rows = db_session.query(WorkflowGroupMembership.group_id).filter_by(user_id=user_id).all()
    return {row[0] for row in rows}

def _may_act(role, group_ids, node):
    if role == 'admin':
        return True
    if node.get('group_id') is None:
        # A generic/unassigned step -- any non-viewer, non-client staff can
        # act on it, same as an admin-or-editor-only legacy transition today.
        return role in ('admin', 'editor')
    return node['group_id'] in group_ids

def _latest_instance(report_id, node_id):
    return (
        db_session.query(ReportStepInstance)
        .filter_by(report_id=report_id, node_id=node_id)
        .order_by(ReportStepInstance.entered_at.desc(), ReportStepInstance.id.desc())
        .first()
    )

def _record_instance(report, node, state, completed_by=None):
    now = datetime.datetime.utcnow()
    instance = ReportStepInstance(
        report_id=report.id,
        node_id=node['id'],
        node_name=node['name'],
        group_id=node.get('group_id'),
        state=state,
        entered_at=now,
        completed_at=now if state == 'done' else None,
        completed_by=completed_by if state == 'done' else None,
    )
    db_session.add(instance)
    # Always flush: this app's session has autoflush=False (see database.py),
    # and a just-recorded instance can immediately gate a later query in the
    # same call -- a join-node predecessor check ('done' rows) or
    # _recompute_status's active_instances() read ('active' rows).
    db_session.flush()
    return instance

def _activate_node(report, nodes_by_id, edges_by_id, node_id, actor_id):
    node = nodes_by_id[node_id]
    if node['type'] in _STRUCTURAL_NODE_TYPES:
        _record_instance(report, node, state='done', completed_by=actor_id)
        for edge in _outgoing_edges(edges_by_id, node_id):
            _activate_node(report, nodes_by_id, edges_by_id, edge['to_node'], actor_id)
        return
    if node['type'] == 'join':
        # AND-join: fires only once every distinct predecessor node (every
        # from_node of an edge into this join) has its most recent instance
        # for this report in state 'done'. Until then, the branch that just
        # finished is simply marked done (already happened, in
        # apply_transition or a prior recursive call) and nothing else
        # activates -- the report sits with some branches done and others
        # still active, which is exactly what allowing multiple simultaneous
        # ReportStepInstance rows exists to represent.
        predecessor_ids = {edge['from_node'] for edge in _edges_into(edges_by_id, node_id)}
        all_done = all(
            (inst := _latest_instance(report.id, pred_id)) is not None and inst.state == 'done'
            for pred_id in predecessor_ids
        )
        if not all_done:
            return
        _record_instance(report, node, state='active')
        return
    # Ordinary 'step' or 'terminal' node -- becomes actionable (or, for a
    # terminal node, simply the report's resting state) until a user fires
    # one of its outgoing edges.
    _record_instance(report, node, state='active')

def get_diagram(report):
    # Authoritative: report.workflow_diagram_id, never "the template's
    # current active diagram" -- editing a diagram must never reach into a
    # report already mid-flight on an earlier version.
    if report.workflow_diagram_id is None:
        return None
    return db_session.query(WorkflowDiagram).get(report.workflow_diagram_id)

def active_instances(report):
    return (
        db_session.query(ReportStepInstance)
        .filter_by(report_id=report.id, state='active')
        .order_by(ReportStepInstance.entered_at)
        .all()
    )

def eligible_actions(report, role, user_id):
    """What can this user do right now on this report? Backs both the
    transition-authorization check in apply_transition and 'what can I do'
    rendering (action buttons, My Queue) -- one function, no duplicated
    eligibility logic between them."""
    diagram = get_diagram(report)
    if diagram is None:
        return []
    nodes_by_id, edges_by_id = _index(diagram)
    group_ids = _group_ids_for(user_id)
    actions = []
    for instance in active_instances(report):
        node = nodes_by_id.get(instance.node_id)
        if node is None or not _may_act(role, group_ids, node):
            continue
        for edge in _outgoing_edges(edges_by_id, instance.node_id):
            actions.append({'edge_id': edge['id'], 'label': edge['action_label'], 'node_id': node['id']})
    return actions

def _recompute_status(report, from_status, actor_id, note):
    actives = active_instances(report)
    if len(actives) == 1:
        report.status = actives[0].node_name
    elif len(actives) == 0:
        # Shouldn't normally happen (a well-formed diagram always leaves the
        # report at an active step or terminal node) -- keep the prior label
        # rather than blank it out.
        report.status = from_status
    else:
        report.status = f"{len(actives)} steps in progress"
    db_session.add(ReportTransition(
        report_id=report.id,
        from_status=from_status,
        to_status=report.status,
        actor_id=actor_id,
        note=note,
    ))

def start_report(report, diagram, actor_id):
    """Seeds a newly created report's initial step instance(s) at its pinned
    diagram's start node. report.workflow_diagram_id must already reference
    `diagram` before this is called."""
    nodes_by_id, edges_by_id = _index(diagram)
    start_node = next(n for n in nodes_by_id.values() if n['type'] == 'start')
    from_status = report.status
    _activate_node(report, nodes_by_id, edges_by_id, start_node['id'], actor_id)
    _recompute_status(report, from_status, actor_id, note=None)
    db_session.commit()
    return report

def apply_transition(report, edge_id, actor_id, note=None):
    diagram = get_diagram(report)
    if diagram is None:
        raise InvalidTransition("Report has no workflow diagram")
    nodes_by_id, edges_by_id = _index(diagram)
    edge = edges_by_id.get(edge_id)
    if edge is None:
        raise InvalidTransition(f"No such edge '{edge_id}' on this report's diagram")

    instance = (
        db_session.query(ReportStepInstance)
        .filter_by(report_id=report.id, node_id=edge['from_node'], state='active')
        .first()
    )
    if instance is None:
        raise InvalidTransition(f"Report has no active step '{edge['from_node']}'")

    actor = db_session.query(User).get(actor_id)
    group_ids = _group_ids_for(actor_id)
    if not _may_act(actor.role, group_ids, nodes_by_id[edge['from_node']]):
        raise NotAuthorized("Not eligible to act on this step")

    from_status = report.status

    instance.state = 'done'
    instance.completed_at = datetime.datetime.utcnow()
    instance.completed_by = actor_id
    instance.action_taken = edge['action_label']
    instance.note = note
    db_session.flush()

    _activate_node(report, nodes_by_id, edges_by_id, edge['to_node'], actor_id)

    _recompute_status(report, from_status, actor_id, note)
    db_session.commit()
    return report
