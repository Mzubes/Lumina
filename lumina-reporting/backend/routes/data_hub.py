from flask import Blueprint, jsonify, request
from database import db_session
from models import FundData
from routes.auth import require_auth

data_hub_blueprint = Blueprint('data_hub', __name__)

@data_hub_blueprint.route('/api/funds', methods=['GET'])
@require_auth()
def get_funds():
    funds = db_session.query(FundData).all()
    return jsonify([fund.serialize() for fund in funds])

@data_hub_blueprint.route('/api/funds', methods=['POST'])
@require_auth(roles=['admin', 'editor'])
def add_fund():
    data = request.get_json(silent=True) or {}
    if not data.get('name') or not data.get('asset_class'):
        return jsonify({'message': 'Name and asset class are required'}), 400
    new_fund = FundData(name=data['name'], asset_class=data['asset_class'])
    db_session.add(new_fund)
    db_session.commit()
    return jsonify({"message": "Fund added successfully"}), 201
