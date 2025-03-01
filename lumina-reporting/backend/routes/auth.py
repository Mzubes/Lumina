from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import jwt, datetime, os
from models import User
from database import db_session

auth_blueprint = Blueprint('auth', __name__)

@auth_blueprint.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json
    user = db_session.query(User).filter_by(email=data['email']).first()
    if not user or not user.check_password(data['password']):
        return jsonify({'message': 'Invalid credentials'}), 401
    token = jwt.encode({
        'user_id': user.id,
        'role': user.role,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=15)
    }, os.environ.get('JWT_SECRET_KEY'), algorithm="HS256")
    return jsonify({'token': token})
