from flask import Blueprint, jsonify

from database import db_session
from models import Report
from routes.auth import require_auth

dashboard_blueprint = Blueprint('dashboard', __name__)

@dashboard_blueprint.get('/api/dashboard')
@require_auth()
def get_dashboard():
    pending_approvals = db_session.query(Report).filter_by(status='review').count()
    recent_reports = (
        db_session.query(Report)
        .order_by(Report.created_at.desc())
        .limit(5)
        .all()
    )
    return jsonify({
        'pendingApprovals': pending_approvals,
        'recentReports': [{'id': report.id, 'name': report.title} for report in recent_reports],
    })
