from flask import Blueprint, g, jsonify, request

from database import db_session
from models import Disclosure, ReportTemplate
from routes.auth import require_auth

disclosures_blueprint = Blueprint('disclosures', __name__)

def _get_disclosure_or_404(disclosure_id):
    return db_session.query(Disclosure).filter_by(id=disclosure_id).first()

@disclosures_blueprint.get('/api/disclosures')
@require_auth()
def list_disclosures():
    disclosures = db_session.query(Disclosure).order_by(Disclosure.title.asc()).all()
    return jsonify([disclosure.serialize() for disclosure in disclosures])

@disclosures_blueprint.get('/api/disclosures/<int:disclosure_id>')
@require_auth()
def get_disclosure(disclosure_id):
    disclosure = _get_disclosure_or_404(disclosure_id)
    if not disclosure:
        return jsonify({'message': 'Disclosure not found'}), 404
    return jsonify(disclosure.serialize())

@disclosures_blueprint.post('/api/disclosures')
@require_auth(roles=['admin', 'editor'])
def create_disclosure():
    data = request.get_json(silent=True) or {}
    title = data.get('title')
    body = data.get('body')
    if not title or not body:
        return jsonify({'message': 'title and body are required'}), 400

    disclosure = Disclosure(
        title=title, body=body, category=data.get('category') or None,
        created_by=g.current_user['user_id'],
    )
    db_session.add(disclosure)
    db_session.commit()
    return jsonify(disclosure.serialize()), 201

@disclosures_blueprint.put('/api/disclosures/<int:disclosure_id>')
@require_auth(roles=['admin', 'editor'])
def update_disclosure(disclosure_id):
    disclosure = _get_disclosure_or_404(disclosure_id)
    if not disclosure:
        return jsonify({'message': 'Disclosure not found'}), 404

    data = request.get_json(silent=True) or {}
    title = data.get('title', disclosure.title)
    body = data.get('body', disclosure.body)
    if not title or not body:
        return jsonify({'message': 'title and body are required'}), 400

    disclosure.title = title
    disclosure.body = body
    disclosure.category = data.get('category', disclosure.category)
    db_session.commit()
    return jsonify(disclosure.serialize())

@disclosures_blueprint.delete('/api/disclosures/<int:disclosure_id>')
@require_auth(roles=['admin', 'editor'])
def delete_disclosure(disclosure_id):
    disclosure = _get_disclosure_or_404(disclosure_id)
    if not disclosure:
        return jsonify({'message': 'Disclosure not found'}), 404

    templates = db_session.query(ReportTemplate).all()
    in_use = any(disclosure_id in template.disclosure_ids_list() for template in templates)
    if in_use:
        return jsonify({'message': 'Cannot delete a disclosure that a template still references'}), 409

    db_session.delete(disclosure)
    db_session.commit()
    return '', 204
