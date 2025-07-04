from flask import Blueprint, jsonify, request
from database import db_session
from models import FundData

data_hub_blueprint = Blueprint('data_hub', __name__)

@data_hub_blueprint.route('/api/funds', methods=['GET'])
def get_funds():
    funds = db_session.query(FundData).all()
    return jsonify([fund.serialize() for fund in funds])

@data_hub_blueprint.route('/api/funds', methods=['POST'])
def add_fund():
    data = request.json
    new_fund = FundData(name=data['name'], asset_class=data['asset_class'])
    db_session.add(new_fund)
    db_session.commit()
    return jsonify({"message": "Fund added successfully"}), 201
