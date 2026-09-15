# One-off rollout migration: generates an auto-equivalent workflow diagram
# for every existing template that doesn't already have one, reproducing
# workflow_legacy.py's exact behavior (draft -> review -> [compliance] ->
# approved -> distributed, with the compliance step's presence gated on
# report_type) -- so nothing changes for any existing report or template
# until a firm actually edits a diagram. Also migrates role='compliance'
# users to a 'Compliance' workflow group + role='editor', and rewrites
# review_role='compliance' component tags to review_group_id.
#
# Simplification versus a fully general conditional-edge engine feature: a
# template whose own reports have used BOTH compliance-required and exempt
# report_types gets the WITH-compliance variant for all of them (the safe
# direction -- it never silently skips a compliance step that used to
# apply). This is the one deliberate behavior difference from the legacy
# engine's exact per-report dynamic branching, accepted because it only
# affects a template with genuinely mixed report_type history, and errs
# toward requiring an extra step rather than skipping one.
import json

from database import db_session
from models import (
    Report, ReportStepInstance, ReportTemplate, ReportTransition,
    User, WorkflowDiagram, WorkflowGroup, WorkflowGroupMembership,
)
from workflow_legacy import COMPLIANCE_REQUIRED_TYPES

COMPLIANCE_GROUP_NAME = 'Compliance'

# Node ids match workflow_legacy's status strings exactly, so an in-flight
# report's current status maps directly onto a node in its generated
# diagram -- 'entry' (the structural start marker) is never a legacy status
# and is never a backfill target.
LEGACY_STATUS_TO_NODE_ID = {
    'draft': 'draft', 'review': 'review', 'compliance': 'compliance',
    'approved': 'approved', 'distributed': 'distributed',
}

def _ensure_compliance_group(system_user_id):
    group = db_session.query(WorkflowGroup).filter_by(name=COMPLIANCE_GROUP_NAME).first()
    if group:
        return group
    group = WorkflowGroup(
        name=COMPLIANCE_GROUP_NAME, created_by=system_user_id,
        description='Auto-created by the workflow-diagrams migration for existing compliance-tagged users/components.',
    )
    db_session.add(group)
    db_session.flush()
    return group

def _migrate_compliance_users(group):
    users = db_session.query(User).filter_by(role='compliance').all()
    for user in users:
        if not db_session.query(WorkflowGroupMembership).filter_by(user_id=user.id, group_id=group.id).first():
            db_session.add(WorkflowGroupMembership(user_id=user.id, group_id=group.id))
        # 'editor', not 'viewer': they could act on assigned work under the
        # legacy role, and demoting to a read-only role would silently strip
        # that. Not 'admin', to avoid silently widening it.
        user.role = 'editor'
    return len(users)

def _migrate_component_review_roles(templates, group):
    count = 0
    for template in templates:
        components = template.components_list()
        changed = False
        for component in components:
            if component.get('review_role') == 'compliance':
                del component['review_role']
                component['review_group_id'] = group.id
                changed = True
                count += 1
        if changed:
            template.components = json.dumps(components)
    return count

def _linear_nodes_edges(with_compliance, compliance_group_id):
    nodes = [
        {'id': 'entry', 'name': 'Start', 'type': 'start', 'group_id': None,
         'position': {'x': 0, 'y': 80}, 'is_distribution_gate': False, 'is_terminal': False},
        {'id': 'draft', 'name': 'Draft', 'type': 'step', 'group_id': None,
         'position': {'x': 200, 'y': 80}, 'is_distribution_gate': False, 'is_terminal': False},
        {'id': 'review', 'name': 'Review', 'type': 'step', 'group_id': None,
         'position': {'x': 400, 'y': 80}, 'is_distribution_gate': False, 'is_terminal': False},
    ]
    edges = [
        {'id': 'e-entry', 'from_node': 'entry', 'to_node': 'draft', 'action_label': 'Start'},
        {'id': 'e-submit', 'from_node': 'draft', 'to_node': 'review', 'action_label': 'Submit'},
        {'id': 'e-reject', 'from_node': 'review', 'to_node': 'draft', 'action_label': 'Reject'},
    ]

    if with_compliance:
        nodes.append({'id': 'compliance', 'name': 'Compliance', 'type': 'step', 'group_id': compliance_group_id,
                       'position': {'x': 600, 'y': 80}, 'is_distribution_gate': False, 'is_terminal': False})
        edges.append({'id': 'e-approve', 'from_node': 'review', 'to_node': 'compliance', 'action_label': 'Approve'})
        edges.append({'id': 'e-request-changes', 'from_node': 'compliance', 'to_node': 'draft', 'action_label': 'Request Changes'})
        approve_from, approve_label, next_x = 'compliance', 'Certify', 800
    else:
        approve_from, approve_label, next_x = 'review', 'Approve', 600

    nodes.append({'id': 'approved', 'name': 'Approved', 'type': 'step', 'group_id': None,
                  'position': {'x': next_x, 'y': 80}, 'is_distribution_gate': False, 'is_terminal': False})
    edges.append({'id': 'e-final-approve', 'from_node': approve_from, 'to_node': 'approved', 'action_label': approve_label})

    nodes.append({'id': 'distributed', 'name': 'Distributed', 'type': 'terminal', 'group_id': None,
                  'position': {'x': next_x + 200, 'y': 80}, 'is_distribution_gate': True, 'is_terminal': True})
    edges.append({'id': 'e-distribute', 'from_node': 'approved', 'to_node': 'distributed', 'action_label': 'Distribute'})

    return nodes, edges

def _template_needs_compliance(template_id):
    types = {
        row[0] for row in
        db_session.query(Report.report_type).filter(Report.template_id == template_id, Report.report_type.isnot(None)).distinct().all()
    }
    if not types:
        return True  # no reports yet -- default to the safer (with-compliance) variant
    return bool(types & COMPLIANCE_REQUIRED_TYPES)

def _backfill_report(report, diagram, nodes_by_id):
    report.workflow_diagram_id = diagram.id
    node = nodes_by_id.get(LEGACY_STATUS_TO_NODE_ID.get(report.status))
    if node is None:
        # Status string doesn't match a known legacy value (shouldn't happen
        # pre-migration) -- pin the diagram id but don't guess a step; the
        # report keeps its current status string as an inert display label.
        return
    latest_transition = (
        db_session.query(ReportTransition)
        .filter_by(report_id=report.id, to_status=report.status)
        .order_by(ReportTransition.created_at.desc())
        .first()
    )
    entered_at = latest_transition.created_at if latest_transition else (report.updated_at or report.created_at)
    db_session.add(ReportStepInstance(
        report_id=report.id, node_id=node['id'], node_name=node['name'], group_id=node.get('group_id'),
        state='active', entered_at=entered_at,
    ))

def migrate_workflow_diagrams(dry_run=False):
    system_user = db_session.query(User).filter_by(role='admin').order_by(User.id).first()
    system_user_id = system_user.id if system_user else 1
    templates = db_session.query(ReportTemplate).all()

    summary = {'compliance_users_migrated': 0, 'components_rewritten': 0, 'templates_migrated': 0, 'reports_backfilled': 0}

    compliance_users_exist = db_session.query(User).filter_by(role='compliance').first() is not None
    any_compliance_component = any(
        component.get('review_role') == 'compliance'
        for template in templates for component in template.components_list()
    )
    group = None
    if compliance_users_exist or any_compliance_component:
        group = _ensure_compliance_group(system_user_id)
    if compliance_users_exist:
        summary['compliance_users_migrated'] = _migrate_compliance_users(group)
    if group:
        summary['components_rewritten'] = _migrate_component_review_roles(templates, group)
    compliance_group_id = group.id if group else None

    for template in templates:
        already_migrated = db_session.query(WorkflowDiagram).filter_by(template_id=template.id, is_active=True).first()
        if already_migrated:
            continue  # never overwrite a hand-authored or previously-generated diagram

        nodes, edges = _linear_nodes_edges(_template_needs_compliance(template.id), compliance_group_id)
        diagram = WorkflowDiagram(
            template_id=template.id, version=1, is_active=True,
            nodes=json.dumps(nodes), edges=json.dumps(edges), generated=True, created_by=system_user_id,
        )
        db_session.add(diagram)
        db_session.flush()
        summary['templates_migrated'] += 1

        nodes_by_id = {n['id']: n for n in nodes}
        reports = db_session.query(Report).filter_by(template_id=template.id, workflow_diagram_id=None).all()
        for report in reports:
            _backfill_report(report, diagram, nodes_by_id)
            summary['reports_backfilled'] += 1

    if dry_run:
        db_session.rollback()
    else:
        db_session.commit()
    return summary
