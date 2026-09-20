from flask import Blueprint, g, jsonify, request

from database import db_session
from models import Holding, PerformanceSnapshot
from routes.auth import require_auth

portfolio_blueprint = Blueprint('portfolio', __name__)

def _resolve_client_id():
    user = g.current_user
    if user.get('role') == 'client':
        return user.get('client_id')
    client_id = request.args.get('client_id', type=int)
    return client_id

@portfolio_blueprint.get('/api/portfolio')
@require_auth()
def get_portfolio():
    client_id = _resolve_client_id()
    if not client_id:
        return jsonify({'message': 'client_id is required'}), 400

    latest_date = (
        db_session.query(Holding.as_of_date)
        .filter_by(client_id=client_id)
        .order_by(Holding.as_of_date.desc())
        .limit(1)
        .scalar()
    )
    holdings = (
        db_session.query(Holding).filter_by(client_id=client_id, as_of_date=latest_date).all()
        if latest_date else []
    )

    snapshots = (
        db_session.query(PerformanceSnapshot)
        .filter_by(client_id=client_id)
        .order_by(PerformanceSnapshot.as_of_date.desc())
        .all()
    )
    latest_by_period = {}
    for snapshot in snapshots:
        latest_by_period.setdefault(snapshot.period_type, snapshot)

    return jsonify({
        'asOfDate': latest_date.isoformat() if latest_date else None,
        'holdings': [holding.serialize() for holding in holdings],
        'performance': [snapshot.serialize() for snapshot in latest_by_period.values()],
    })
