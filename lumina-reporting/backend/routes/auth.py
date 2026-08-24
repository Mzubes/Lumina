from functools import wraps
import datetime

import jwt
from flask import Blueprint, current_app, g, jsonify, request

from database import db_session
from models import User

auth_blueprint = Blueprint('auth', __name__)

def require_auth(roles=None):
    allowed_roles = set(roles or [])
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            header = request.headers.get('Authorization', '')
            if not header.startswith('Bearer '):
                return jsonify({'message': 'Authentication required'}), 401
            try:
                payload = jwt.decode(
                    header.removeprefix('Bearer ').strip(),
                    current_app.config['JWT_SECRET_KEY'],
                    algorithms=['HS256'],
                )
            except jwt.PyJWTError:
                return jsonify({'message': 'Invalid or expired token'}), 401
            if allowed_roles and payload.get('role') not in allowed_roles:
                return jsonify({'message': 'Insufficient permissions'}), 403
            g.current_user = payload
            return view(*args, **kwargs)
        return wrapped
    return decorator

@auth_blueprint.post('/api/auth/login')
def login():
    data = request.get_json(silent=True) or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    if not email or not password:
        return jsonify({'message': 'Email and password are required'}), 400
    user = db_session.query(User).filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({'message': 'Invalid credentials'}), 401
    token = jwt.encode({
        'user_id': user.id,
        'role': user.role,
        'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=15),
    }, current_app.config['JWT_SECRET_KEY'], algorithm='HS256')
    return jsonify({'token': token})
