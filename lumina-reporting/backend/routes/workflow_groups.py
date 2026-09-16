from flask import Blueprint, g, jsonify, request
from sqlalchemy import func

from database import db_session
from models import ReportTemplate, User, WorkflowDiagram, WorkflowGroup, WorkflowGroupMembership
from routes.auth import require_auth

workflow_groups_blueprint = Blueprint('workflow_groups', __name__)

def _get_group_or_404(group_id):
    return db_session.query(WorkflowGroup).filter_by(id=group_id).first()

def _templates_referencing_group(group_id):
    # nodes is JSON-as-Text (see models.py/WorkflowDiagram) -- there's no
    # portable way to query into it in SQL, so this scans active diagrams in
    # Python, the same accepted-cost pattern reviewable_components() already
    # uses for template component JSON elsewhere in this codebase.
    diagrams = db_session.query(WorkflowDiagram).filter_by(is_active=True).all()
    template_ids = {d.template_id for d in diagrams if any(n.get('group_id') == group_id for n in d.nodes_list())}
    if not template_ids:
        return []
    templates = db_session.query(ReportTemplate).filter(ReportTemplate.id.in_(template_ids)).all()
    return [t.name for t in templates]

@workflow_groups_blueprint.get('/api/workflow-groups')
@require_auth(roles=['admin', 'editor', 'viewer'])
def list_groups():
    groups = db_session.query(WorkflowGroup).order_by(WorkflowGroup.name.asc()).all()
    counts = dict(
        db_session.query(WorkflowGroupMembership.group_id, func.count(WorkflowGroupMembership.id))
        .group_by(WorkflowGroupMembership.group_id).all()
    )
    return jsonify([{**group.serialize(), 'member_count': counts.get(group.id, 0)} for group in groups])

@workflow_groups_blueprint.post('/api/workflow-groups')
@require_auth(roles=['admin'])
def create_group():
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'message': 'name is required'}), 400
    if db_session.query(WorkflowGroup).filter_by(name=name).first():
        return jsonify({'message': 'A group with that name already exists'}), 400

    group = WorkflowGroup(name=name, description=data.get('description') or None, created_by=g.current_user['user_id'])
    db_session.add(group)
    db_session.commit()
    return jsonify(group.serialize()), 201

@workflow_groups_blueprint.put('/api/workflow-groups/<int:group_id>')
@require_auth(roles=['admin'])
def update_group(group_id):
    group = _get_group_or_404(group_id)
    if not group:
        return jsonify({'message': 'Group not found'}), 404

    data = request.get_json(silent=True) or {}
    name = (data.get('name', group.name) or '').strip()
    if not name:
        return jsonify({'message': 'name is required'}), 400
    if name != group.name and db_session.query(WorkflowGroup).filter_by(name=name).first():
        return jsonify({'message': 'A group with that name already exists'}), 400

    group.name = name
    group.description = data.get('description', group.description)
    db_session.commit()
    return jsonify(group.serialize())

@workflow_groups_blueprint.delete('/api/workflow-groups/<int:group_id>')
@require_auth(roles=['admin'])
def delete_group(group_id):
    group = _get_group_or_404(group_id)
    if not group:
        return jsonify({'message': 'Group not found'}), 404

    referencing = _templates_referencing_group(group_id)
    if referencing:
        return jsonify({
            'message': f"Cannot delete: this group is assigned to a step in the workflow for {', '.join(referencing)}",
        }), 409

    db_session.query(WorkflowGroupMembership).filter_by(group_id=group_id).delete()
    db_session.delete(group)
    db_session.commit()
    return '', 204

@workflow_groups_blueprint.get('/api/workflow-groups/<int:group_id>/members')
@require_auth(roles=['admin', 'editor', 'viewer'])
def list_group_members(group_id):
    group = _get_group_or_404(group_id)
    if not group:
        return jsonify({'message': 'Group not found'}), 404
    members = (
        db_session.query(User)
        .join(WorkflowGroupMembership, WorkflowGroupMembership.user_id == User.id)
        .filter(WorkflowGroupMembership.group_id == group_id)
        .order_by(User.email.asc())
        .all()
    )
    return jsonify([user.serialize() for user in members])

@workflow_groups_blueprint.post('/api/workflow-groups/<int:group_id>/members')
@require_auth(roles=['admin'])
def add_group_member(group_id):
    group = _get_group_or_404(group_id)
    if not group:
        return jsonify({'message': 'Group not found'}), 404

    data = request.get_json(silent=True) or {}
    user_id = data.get('user_id')
    user = db_session.query(User).filter_by(id=user_id).first() if user_id else None
    if not user:
        return jsonify({'message': 'Unknown user_id'}), 400
    if db_session.query(WorkflowGroupMembership).filter_by(user_id=user_id, group_id=group_id).first():
        return jsonify({'message': 'User is already a member of this group'}), 400

    membership = WorkflowGroupMembership(user_id=user_id, group_id=group_id)
    db_session.add(membership)
    db_session.commit()
    return jsonify(membership.serialize()), 201

@workflow_groups_blueprint.delete('/api/workflow-groups/<int:group_id>/members/<int:user_id>')
@require_auth(roles=['admin'])
def remove_group_member(group_id, user_id):
    membership = db_session.query(WorkflowGroupMembership).filter_by(group_id=group_id, user_id=user_id).first()
    if not membership:
        return jsonify({'message': 'Membership not found'}), 404
    db_session.delete(membership)
    db_session.commit()
    return '', 204
