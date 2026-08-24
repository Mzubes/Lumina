from flask import Blueprint, jsonify
from routes.auth import require_auth

dashboard_blueprint = Blueprint('dashboard', __name__)

@dashboard_blueprint.get('/api/dashboard')
@require_auth()
def get_dashboard():
    return jsonify({
        'pendingApprovals': 1,
        'recentReports': [
            {'id': 1, 'name': 'Q2 Institutional Portfolio Report'},
            {'id': 2, 'name': 'July Performance Summary'},
        ],
    })
