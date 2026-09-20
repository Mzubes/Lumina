import datetime

from flask import Blueprint, jsonify
from sqlalchemy import func

from database import db_session
from models import Client, ComponentReview, DataSource, FundData, Report
import production_metrics
from report_content import reviewable_components
from routes.auth import require_auth

dashboard_blueprint = Blueprint('dashboard', __name__)

REPORT_STATUSES = ['draft', 'review', 'compliance', 'approved', 'distributed']
TOP_N = 6
REPORTS_BY_WEEK_WINDOW = 8

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

def _reports_by_week(weeks=REPORTS_BY_WEEK_WINDOW):
    """Real (not synthetic) weekly volume, zero-filled so the chart always
    has exactly `weeks` bars. Bucketed in Python via isocalendar() rather
    than SQL -- dev is SQLite, prod is Postgres, and week-bucketing
    functions aren't portable between the two."""
    since = datetime.datetime.utcnow() - datetime.timedelta(weeks=weeks)
    created_ats = [
        row[0] for row in
        db_session.query(Report.created_at).filter(Report.created_at.isnot(None), Report.created_at >= since).all()
    ]
    counts = {}
    for created_at in created_ats:
        year, week, _ = created_at.isocalendar()
        counts[(year, week)] = counts.get((year, week), 0) + 1

    now = datetime.datetime.utcnow()
    result = []
    for offset in range(weeks - 1, -1, -1):
        year, week, _ = (now - datetime.timedelta(weeks=offset)).isocalendar()
        result.append({'label': f'W{week}', 'count': counts.get((year, week), 0)})
    return result

def _missing_content():
    """Reviewable components with no matching ComponentReview row, scoped to
    reports still in flight (review/compliance) -- same scoping as
    pendingApprovals/pendingCompliance below, so this means 'needs action
    now', not 'ever needed review'. One ReportTemplate fetch per report (via
    reviewable_components) -- accepted N+1 at demo scale.

    Returns the gaps themselves rather than just a tally: the count is one
    len() away, and the Production Hub's list needs to say which report is
    missing what, not only how many are."""
    in_flight_reports = (
        db_session.query(Report)
        .filter(Report.template_id.isnot(None), Report.status.in_(['review', 'compliance']))
        .all()
    )
    if not in_flight_reports:
        return []
    reviewed = {
        (row.report_id, row.component_id) for row in
        db_session.query(ComponentReview.report_id, ComponentReview.component_id)
        .filter(ComponentReview.report_id.in_([report.id for report in in_flight_reports]))
        .all()
    }
    return [
        {
            'reportId': report.id,
            'reportTitle': report.title,
            'componentId': component['id'],
            'componentLabel': component.get('title') or component.get('type') or component['id'],
        }
        for report in in_flight_reports
        for component in reviewable_components(report)
        if (report.id, component['id']) not in reviewed
    ]

@dashboard_blueprint.get('/api/dashboard')
@require_auth()
def get_dashboard():
    pending_approvals = db_session.query(Report).filter_by(status='review').count()
    pending_compliance = db_session.query(Report).filter_by(status='compliance').count()

    status_counts = dict(
        db_session.query(Report.status, func.count(Report.id)).group_by(Report.status).all()
    )
    # The 5 legacy keys are always present (even at 0, for stable chart
    # rendering); a firm-customized workflow step introduces additional keys
    # this dict was never written to anticipate -- keep those too rather
    # than silently dropping their counts.
    reports_by_status = {status: status_counts.get(status, 0) for status in REPORT_STATUSES}
    reports_by_status.update({status: count for status, count in status_counts.items() if status not in REPORT_STATUSES})

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

    # The whole roster, not only the broken ones: a source that has never
    # synced is its own kind of problem, and "all green" is only meaningful
    # if you can see what was checked. failedDataSources stays as its own
    # key -- the alert banner and several existing callers read it.
    data_sources = [
        {
            'id': source.id,
            'name': source.name,
            'type': source.type,
            'status': source.last_sync_status or 'never',
            'message': source.last_sync_message,
            'lastSyncedAt': source.last_synced_at.isoformat() if source.last_synced_at else None,
        }
        for source in db_session.query(DataSource).order_by(DataSource.name.asc()).all()
    ]
    failed_data_sources = [
        {'id': source['id'], 'name': source['name'], 'message': source['message']}
        for source in data_sources if source['status'] == 'error'
    ]

    missing_content = _missing_content()

    recent_reports = (
        db_session.query(Report)
        .order_by(Report.created_at.desc())
        .limit(5)
        .all()
    )
    return jsonify({
        'pendingApprovals': pending_approvals,
        'pendingCompliance': pending_compliance,
        'totalReports': sum(reports_by_status.values()),
        'reportsByStatus': reports_by_status,
        'reportsByTeam': _top_n_with_other(team_rows),
        'reportsByAssetClass': _top_n_with_other(asset_class_rows),
        'reportsByClient': _top_n_with_other(client_rows),
        'failedDataSources': failed_data_sources,
        'recentReports': [{'id': report.id, 'name': report.title} for report in recent_reports],
        'reportsByWeek': _reports_by_week(),
        'pendingComponentReviews': len(missing_content),
        'missingContent': missing_content,
        'dataSources': data_sources,
        'workflowStageProgress': production_metrics.workflow_stage_progress(),
        'slaAtRisk': production_metrics.sla_at_risk(),
        'deliverySla': production_metrics.delivery_sla(),
        'upcomingDeadlines': production_metrics.upcoming_deadlines(),
    })


@dashboard_blueprint.get('/api/dashboard/management')
@require_auth(roles=['admin', 'editor', 'viewer'])
def get_management_dashboard():
    """The Management tab's aggregates, on their own endpoint.

    These scan every step instance and every report's workflow diagram, so
    they're deliberately not folded into /api/dashboard -- that payload is
    fetched on every visit to the Production Hub, and this one only when
    somebody opens the tab that shows it."""
    return jsonify({
        'slowestSteps': production_metrics.slowest_steps(),
        'bottleneckByGroup': production_metrics.bottleneck_by_group(),
        'teamScorecard': production_metrics.team_scorecard(),
        'minVisitsForAverage': production_metrics.MIN_VISITS_FOR_AVERAGE,
    })
