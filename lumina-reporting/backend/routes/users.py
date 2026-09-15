from flask import Blueprint, g, jsonify, request
from sqlalchemy.exc import IntegrityError

from database import db_session
from models import Client, User
from routes.auth import require_auth

users_blueprint = Blueprint('users', __name__)

# Mirrors the role vocabulary app.py's `create-user` CLI command already
# enforces -- the only other place this was validated before this route
# existed.
VALID_ROLES = {'admin', 'editor', 'viewer', 'compliance', 'client'}
MIN_PASSWORD_LENGTH = 8

def _get_user_or_404(user_id):
    return db_session.query(User).filter_by(id=user_id).first()

def _admin_count():
    return db_session.query(User).filter_by(role='admin').count()

def _validate_role_and_client(role, client_id):
    if role not in VALID_ROLES:
        return f"role must be one of {sorted(VALID_ROLES)}"
    if role == 'client':
        if client_id is None:
            return 'client_id is required when role is client'
        if not db_session.query(Client).filter_by(id=client_id).first():
            return 'Unknown client_id'
    return None

@users_blueprint.get('/api/users')
@require_auth(roles=['admin'])
def list_users():
    users = db_session.query(User).order_by(User.email.asc()).all()
    return jsonify([user.serialize() for user in users])

@users_blueprint.get('/api/users/<int:user_id>')
@require_auth(roles=['admin'])
def get_user(user_id):
    user = _get_user_or_404(user_id)
    if not user:
        return jsonify({'message': 'User not found'}), 404
    return jsonify(user.serialize())

@users_blueprint.post('/api/users')
@require_auth(roles=['admin'])
def create_user():
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    role = data.get('role')
    client_id = data.get('client_id')
    password = data.get('password') or ''

    if not email:
        return jsonify({'message': 'email is required'}), 400
    error = _validate_role_and_client(role, client_id)
    if error:
        return jsonify({'message': error}), 400
    if len(password) < MIN_PASSWORD_LENGTH:
        return jsonify({'message': f'password must be at least {MIN_PASSWORD_LENGTH} characters'}), 400
    if db_session.query(User).filter_by(email=email).first():
        return jsonify({'message': 'A user with that email already exists'}), 400

    user = User(email=email, role=role, client_id=client_id if role == 'client' else None)
    user.set_password(password)
    db_session.add(user)
    db_session.commit()
    return jsonify(user.serialize()), 201

@users_blueprint.put('/api/users/<int:user_id>')
@require_auth(roles=['admin'])
def update_user(user_id):
    user = _get_user_or_404(user_id)
    if not user:
        return jsonify({'message': 'User not found'}), 404

    data = request.get_json(silent=True) or {}
    email = data.get('email', user.email)
    if isinstance(email, str):
        email = email.strip().lower()
    role = data.get('role', user.role)
    client_id = data.get('client_id', user.client_id)

    if not email:
        return jsonify({'message': 'email is required'}), 400
    error = _validate_role_and_client(role, client_id)
    if error:
        return jsonify({'message': error}), 400
    if email != user.email and db_session.query(User).filter_by(email=email).first():
        return jsonify({'message': 'A user with that email already exists'}), 400
    if user.role == 'admin' and role != 'admin' and _admin_count() <= 1:
        return jsonify({'message': 'Cannot change the role of the last remaining admin'}), 409

    user.email = email
    user.role = role
    user.client_id = client_id if role == 'client' else None

    password = data.get('password')
    if password:
        if len(password) < MIN_PASSWORD_LENGTH:
            return jsonify({'message': f'password must be at least {MIN_PASSWORD_LENGTH} characters'}), 400
        user.set_password(password)

    db_session.commit()
    return jsonify(user.serialize())

@users_blueprint.delete('/api/users/<int:user_id>')
@require_auth(roles=['admin'])
def delete_user(user_id):
    user = _get_user_or_404(user_id)
    if not user:
        return jsonify({'message': 'User not found'}), 404
    if user.id == g.current_user['user_id']:
        return jsonify({'message': "You can't delete your own account"}), 400
    if user.role == 'admin' and _admin_count() <= 1:
        return jsonify({'message': 'Cannot delete the last remaining admin'}), 409

    db_session.delete(user)
    try:
        db_session.commit()
    except IntegrityError:
        db_session.rollback()
        return jsonify({'message': 'Cannot delete a user with existing reports or activity tied to them'}), 409
    return '', 204
