import json

from flask import Blueprint, g, jsonify, request

from database import db_session
from models import ReportTemplate, WorkflowDiagram
from routes.auth import require_auth
from workflow_diagram_validation import validate_diagram

workflow_diagrams_blueprint = Blueprint('workflow_diagrams', __name__)

def _get_template_or_404(template_id):
    return db_session.query(ReportTemplate).filter_by(id=template_id).first()

def _active_diagram(template_id):
    return db_session.query(WorkflowDiagram).filter_by(template_id=template_id, is_active=True).first()

@workflow_diagrams_blueprint.get('/api/templates/<int:template_id>/workflow')
@require_auth(roles=['admin', 'editor', 'viewer'])
def get_workflow(template_id):
    if not _get_template_or_404(template_id):
        return jsonify({'message': 'Template not found'}), 404
    diagram = _active_diagram(template_id)
    return jsonify(diagram.serialize() if diagram else None)

@workflow_diagrams_blueprint.put('/api/templates/<int:template_id>/workflow')
@require_auth(roles=['admin'])
def save_workflow(template_id):
    if not _get_template_or_404(template_id):
        return jsonify({'message': 'Template not found'}), 404

    data = request.get_json(silent=True) or {}
    nodes, edges = data.get('nodes'), data.get('edges')
    error = validate_diagram(nodes, edges)
    if error:
        return jsonify({'message': error}), 400

    latest = (
        db_session.query(WorkflowDiagram.version)
        .filter_by(template_id=template_id)
        .order_by(WorkflowDiagram.version.desc())
        .first()
    )
    next_version = (latest[0] + 1) if latest else 1

    # Atomic: deactivate whatever was active and activate the new version in
    # the same transaction, so a reader never sees zero or two active
    # diagrams for this template. An in-flight report stays pinned to
    # whichever diagram id it already has (Report.workflow_diagram_id) --
    # this never touches that column.
    db_session.query(WorkflowDiagram).filter_by(template_id=template_id, is_active=True).update({'is_active': False})
    diagram = WorkflowDiagram(
        template_id=template_id, version=next_version, is_active=True,
        nodes=json.dumps(nodes), edges=json.dumps(edges), generated=False,
        created_by=g.current_user['user_id'],
    )
    db_session.add(diagram)
    db_session.commit()
    return jsonify(diagram.serialize()), 201

@workflow_diagrams_blueprint.get('/api/templates/<int:template_id>/workflow/history')
@require_auth(roles=['admin'])
def get_workflow_history(template_id):
    if not _get_template_or_404(template_id):
        return jsonify({'message': 'Template not found'}), 404
    diagrams = (
        db_session.query(WorkflowDiagram).filter_by(template_id=template_id)
        .order_by(WorkflowDiagram.version.desc()).all()
    )
    return jsonify([diagram.serialize() for diagram in diagrams])
