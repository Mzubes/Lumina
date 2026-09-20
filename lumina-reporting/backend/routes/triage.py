"""The four counts behind the start screen.

One endpoint rather than four round-trips: these are small aggregate counts
rendered together on a single screen, same convention as /api/dashboard and
/api/book.

Every count is derived from data the app already records. Nothing here
invents a signal -- in particular there is deliberately no "missing data"
half to the stuck count, because no report -> data-source relationship
exists in the model to derive it from (a template's data bindings name
datasets, not sources). Failed sources are surfaced on their own, on the
Production Hub.

The "stuck" and "overdue" definitions live in report_filters so that the
counts here and the filtered lists the cards link to (/api/reports?stuck=1,
?overdue=1) can never disagree.
"""

from flask import Blueprint, g, jsonify

import report_filters
import workflow_engine
from database import db_session
from models import Report
from routes.auth import require_auth
from routes.reports import build_my_queue

triage_blueprint = Blueprint('triage', __name__)


@triage_blueprint.get('/api/triage')
@require_auth(roles=['admin', 'editor', 'viewer'])
def get_triage():
    role = g.current_user.get('role')
    user_id = g.current_user['user_id']

    reports = db_session.query(Report).all()
    open_reports = [report for report in reports if report_filters.is_open(report)]

    ready = [
        report for report in open_reports
        if workflow_engine.can_distribute_now(report, role, user_id)
    ]

    return jsonify({
        'respondingCount': len(build_my_queue(role, user_id)),
        'stuckCount': len(report_filters.stuck_reports(open_reports)),
        'overdueCount': len(report_filters.overdue_reports(open_reports)),
        'readyToDistributeCount': len(ready),
        'staleAfterDays': report_filters.STALE_AFTER_DAYS,
    })
