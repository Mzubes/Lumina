from flask import Blueprint, jsonify
from sqlalchemy import func

from database import db_session
from models import Report
from routes.auth import require_auth

dashboard_blueprint = Blueprint('dashboard', __name__)

REPORT_STATUSES = ['draft', 'review', 'approved', 'distributed']

@dashboard_blueprint.get('/api/dashboard')
@require_auth()
def get_dashboard():
    pending_approvals = db_session.query(Report).filter_by(status='review').count()

    status_counts = dict(
        db_session.query(Report.status, func.count(Report.id)).group_by(Report.status).all()
    )
    reports_by_status = {status: status_counts.get(status, 0) for status in REPORT_STATUSES}

    recent_reports = (
        db_session.query(Report)
        .order_by(Report.created_at.desc())
        .limit(5)
        .all()
    )
    return jsonify({
        'pendingApprovals': pending_approvals,
        'totalReports': sum(reports_by_status.values()),
        'reportsByStatus': reports_by_status,
        'recentReports': [{'id': report.id, 'name': report.title} for report in recent_reports],
    })
