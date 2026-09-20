from flask import Blueprint, g, jsonify, request

from database import db_session
from models import Client, Contact, Report, User
from routes.auth import require_auth

clients_blueprint = Blueprint('clients', __name__)

def _get_client_or_404(client_id):
    return db_session.query(Client).filter_by(id=client_id).first()

def _get_contact_or_404(client_id, contact_id):
    return db_session.query(Contact).filter_by(id=contact_id, client_id=client_id).first()

def _validate_relationship_manager(raw_id):
    """-> (value, error). Explicit null clears the assignment. A client-portal
    user can't own a relationship -- they're the other side of it -- so only
    staff accounts are accepted."""
    if raw_id is None:
        return None, None
    user = db_session.query(User).filter_by(id=raw_id).first()
    if not user:
        return None, 'relationship_manager_id must reference an existing user'
    if user.role == 'client':
        return None, 'A client-portal user cannot be a relationship manager'
    return user.id, None

@clients_blueprint.get('/api/clients')
@require_auth(roles=['admin', 'editor', 'viewer'])
def list_clients():
    clients = db_session.query(Client).order_by(Client.name.asc()).all()
    return jsonify([client.serialize() for client in clients])

@clients_blueprint.get('/api/clients/<int:client_id>')
@require_auth(roles=['admin', 'editor', 'viewer'])
def get_client(client_id):
    client = _get_client_or_404(client_id)
    if not client:
        return jsonify({'message': 'Client not found'}), 404
    return jsonify(client.serialize())

@clients_blueprint.post('/api/clients')
@require_auth(roles=['admin', 'editor'])
def create_client():
    data = request.get_json(silent=True) or {}
    name = data.get('name')
    if not name:
        return jsonify({'message': 'name is required'}), 400

    manager_id, error = _validate_relationship_manager(data.get('relationship_manager_id'))
    if error:
        return jsonify({'message': error}), 400

    client = Client(
        name=name, contact_email=data.get('contact_email') or None,
        relationship_manager_id=manager_id,
    )
    db_session.add(client)
    db_session.commit()
    return jsonify(client.serialize()), 201

@clients_blueprint.put('/api/clients/<int:client_id>')
@require_auth(roles=['admin', 'editor'])
def update_client(client_id):
    client = _get_client_or_404(client_id)
    if not client:
        return jsonify({'message': 'Client not found'}), 404

    data = request.get_json(silent=True) or {}
    name = data.get('name', client.name)
    if not name:
        return jsonify({'message': 'name is required'}), 400

    client.name = name
    client.contact_email = data.get('contact_email', client.contact_email)
    # Absent key leaves the assignment alone; an explicit null clears it.
    if 'relationship_manager_id' in data:
        manager_id, error = _validate_relationship_manager(data['relationship_manager_id'])
        if error:
            return jsonify({'message': error}), 400
        client.relationship_manager_id = manager_id
    db_session.commit()
    return jsonify(client.serialize())

@clients_blueprint.delete('/api/clients/<int:client_id>')
@require_auth(roles=['admin'])
def delete_client(client_id):
    client = _get_client_or_404(client_id)
    if not client:
        return jsonify({'message': 'Client not found'}), 404

    in_use = (
        db_session.query(Report).filter_by(client_id=client_id).first()
        or db_session.query(User).filter_by(client_id=client_id).first()
    )
    if in_use:
        return jsonify({'message': 'Cannot delete a client that has reports or users tied to it'}), 409

    for contact in db_session.query(Contact).filter_by(client_id=client_id).all():
        db_session.delete(contact)
    db_session.delete(client)
    db_session.commit()
    return '', 204

@clients_blueprint.get('/api/clients/<int:client_id>/contacts')
@require_auth(roles=['admin', 'editor', 'viewer'])
def list_contacts(client_id):
    if not _get_client_or_404(client_id):
        return jsonify({'message': 'Client not found'}), 404
    contacts = db_session.query(Contact).filter_by(client_id=client_id).order_by(Contact.name.asc()).all()
    return jsonify([contact.serialize() for contact in contacts])

@clients_blueprint.post('/api/clients/<int:client_id>/contacts')
@require_auth(roles=['admin', 'editor'])
def create_contact(client_id):
    if not _get_client_or_404(client_id):
        return jsonify({'message': 'Client not found'}), 404

    data = request.get_json(silent=True) or {}
    name = data.get('name')
    if not name:
        return jsonify({'message': 'name is required'}), 400

    contact = Contact(
        client_id=client_id, name=name, email=data.get('email') or None,
        title=data.get('title') or None, phone=data.get('phone') or None,
    )
    db_session.add(contact)
    db_session.commit()
    return jsonify(contact.serialize()), 201

@clients_blueprint.put('/api/clients/<int:client_id>/contacts/<int:contact_id>')
@require_auth(roles=['admin', 'editor'])
def update_contact(client_id, contact_id):
    contact = _get_contact_or_404(client_id, contact_id)
    if not contact:
        return jsonify({'message': 'Contact not found'}), 404

    data = request.get_json(silent=True) or {}
    name = data.get('name', contact.name)
    if not name:
        return jsonify({'message': 'name is required'}), 400

    contact.name = name
    contact.email = data.get('email', contact.email)
    contact.title = data.get('title', contact.title)
    contact.phone = data.get('phone', contact.phone)
    db_session.commit()
    return jsonify(contact.serialize())

@clients_blueprint.delete('/api/clients/<int:client_id>/contacts/<int:contact_id>')
@require_auth(roles=['admin', 'editor'])
def delete_contact(client_id, contact_id):
    contact = _get_contact_or_404(client_id, contact_id)
    if not contact:
        return jsonify({'message': 'Contact not found'}), 404

    db_session.delete(contact)
    db_session.commit()
    return '', 204
