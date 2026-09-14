import json

from flask import Blueprint, g, jsonify, request

from database import db_session
from models import Report, ReportTemplate
from routes.auth import require_auth
from template_components import validate_components

templates_blueprint = Blueprint('templates', __name__)

def _get_template_or_404(template_id):
    return db_session.query(ReportTemplate).filter_by(id=template_id).first()

@templates_blueprint.get('/api/templates')
@require_auth()
def list_templates():
    templates = db_session.query(ReportTemplate).order_by(ReportTemplate.name.asc()).all()
    return jsonify([template.serialize() for template in templates])

@templates_blueprint.get('/api/templates/<int:template_id>')
@require_auth()
def get_template(template_id):
    template = _get_template_or_404(template_id)
    if not template:
        return jsonify({'message': 'Template not found'}), 404
    return jsonify(template.serialize())

@templates_blueprint.post('/api/templates')
@require_auth(roles=['admin', 'editor'])
def create_template():
    data = request.get_json(silent=True) or {}
    name = data.get('name')
    components = data.get('components')
    if not name:
        return jsonify({'message': 'name is required'}), 400
    error = validate_components(components)
    if error:
        return jsonify({'message': error}), 400

    template = ReportTemplate(
        name=name,
        description=data.get('description'),
        components=json.dumps(components),
        created_by=g.current_user['user_id'],
    )
    db_session.add(template)
    db_session.commit()
    return jsonify(template.serialize()), 201

@templates_blueprint.put('/api/templates/<int:template_id>')
@require_auth(roles=['admin', 'editor'])
def update_template(template_id):
    template = _get_template_or_404(template_id)
    if not template:
        return jsonify({'message': 'Template not found'}), 404

    data = request.get_json(silent=True) or {}
    name = data.get('name', template.name)
    components = data.get('components', template.components_list())
    if not name:
        return jsonify({'message': 'name is required'}), 400
    error = validate_components(components)
    if error:
        return jsonify({'message': error}), 400

    template.name = name
    template.description = data.get('description', template.description)
    template.components = json.dumps(components)
    db_session.commit()
    return jsonify(template.serialize())

@templates_blueprint.delete('/api/templates/<int:template_id>')
@require_auth(roles=['admin', 'editor'])
def delete_template(template_id):
    template = _get_template_or_404(template_id)
    if not template:
        return jsonify({'message': 'Template not found'}), 404

    in_use = db_session.query(Report).filter_by(template_id=template_id).first()
    if in_use:
        return jsonify({'message': 'Cannot delete a template that has reports using it'}), 409

    db_session.delete(template)
    db_session.commit()
    return '', 204
