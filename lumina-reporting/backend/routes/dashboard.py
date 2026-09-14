from flask import Blueprint, jsonify
from sqlalchemy import func

from database import db_session
from models import Client, DataSource, FundData, Report
from routes.auth import require_auth

dashboard_blueprint = Blueprint('dashboard', __name__)

REPORT_STATUSES = ['draft', 'review', 'approved', 'distributed']
TOP_N = 6

def _top_n_with_other(rows, other_label='Other', unassigned_label='Unassigned'):
    """rows: list of (label_or_None, count). Keeps the top N named labels by
    count, folds the rest into one 'Other' bucket, and any null/blank label
    into 'Unassigned' -- matches the dataviz skill's series-count ladder
    (fold past ~6-8 rather than growing colors indefinitely)."""
    named = sorted(((label, count) for label, count in rows if label), key=lambda row: row[1], reverse=True)
    unassigned_count = sum(count for label, count in rows if not label)

    result = [{'label': label, 'count': count} for label, count in named[:TOP_N]]
    overflow = sum(count for _, count in named[TOP_N:])
    if overflow:
        result.append({'label': other_label, 'count': overflow})
    if unassigned_count:
        result.append({'label': unassigned_label, 'count': unassigned_count})
    return result

@dashboard_blueprint.get('/api/dashboard')
@require_auth()
def get_dashboard():
    pending_approvals = db_session.query(Report).filter_by(status='review').count()

    status_counts = dict(
        db_session.query(Report.status, func.count(Report.id)).group_by(Report.status).all()
    )
    reports_by_status = {status: status_counts.get(status, 0) for status in REPORT_STATUSES}

    team_rows = db_session.query(Report.team, func.count(Report.id)).group_by(Report.team).all()
    asset_class_rows = (
        db_session.query(FundData.asset_class, func.count(Report.id))
        .select_from(Report)
        .outerjoin(FundData, Report.fund_id == FundData.id)
        .group_by(FundData.asset_class)
        .all()
    )
    client_rows = (
        db_session.query(Client.name, func.count(Report.id))
        .select_from(Report)
        .join(Client, Report.client_id == Client.id)
        .group_by(Client.name)
        .all()
    )

    failed_data_sources = [
        {'id': source.id, 'name': source.name, 'message': source.last_sync_message}
        for source in db_session.query(DataSource).filter_by(last_sync_status='error').all()
    ]

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
        'reportsByTeam': _top_n_with_other(team_rows),
        'reportsByAssetClass': _top_n_with_other(asset_class_rows),
        'reportsByClient': _top_n_with_other(client_rows),
        'failedDataSources': failed_data_sources,
        'recentReports': [{'id': report.id, 'name': report.title} for report in recent_reports],
    })
