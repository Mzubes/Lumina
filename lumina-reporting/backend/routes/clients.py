from flask import Blueprint, jsonify

from database import db_session
from models import Client
from routes.auth import require_auth

clients_blueprint = Blueprint('clients', __name__)

@clients_blueprint.get('/api/clients')
@require_auth(roles=['admin', 'editor', 'viewer'])
def list_clients():
    clients = db_session.query(Client).order_by(Client.name.asc()).all()
    return jsonify([client.serialize() for client in clients])
