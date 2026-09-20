"""Shared "is this report stuck / overdue" predicates.

These live outside the route modules because two of them need the same
answer: /api/triage counts them, and /api/reports filters by them (the
start screen's cards link straight to those filtered lists, so a count and
the list it opens have to be derived from one definition, not two).

Neither predicate is expressible as a plain SQLAlchemy filter -- "open"
means `workflow_engine.report_is_distributed` is false, which reads the
report's diagram, and "stuck" needs the last transition per report. Both
are therefore applied in Python over an already-fetched list.
"""

import datetime

from sqlalchemy import func

from database import db_session
from models import ReportTransition
import workflow_engine

# How long a report can sit with no workflow movement before it's "stuck".
STALE_AFTER_DAYS = 3


def is_open(report):
    """Everything not yet delivered. A report that's gone out can't be
    overdue, stuck, or waiting to be distributed."""
    return not workflow_engine.report_is_distributed(report)


def last_movement_by_report():
    """report_id -> most recent transition time. Fetched once for a whole
    list rather than per report."""
    rows = (
        db_session.query(ReportTransition.report_id, func.max(ReportTransition.created_at))
        .group_by(ReportTransition.report_id)
        .all()
    )
    return {report_id: last for report_id, last in rows}


def stuck_reports(reports, now=None, last_movement=None):
    now = now or datetime.datetime.utcnow()
    stale_before = now - datetime.timedelta(days=STALE_AFTER_DAYS)
    movements = last_movement if last_movement is not None else last_movement_by_report()
    # Falls back to creation time so a brand-new draft nobody has touched
    # still ages into "stuck" -- it has no transitions at all.
    return [
        report for report in reports
        if is_open(report) and (movements.get(report.id) or report.created_at or now) < stale_before
    ]


def overdue_reports(reports, today=None):
    today = today or datetime.date.today()
    return [
        report for report in reports
        if is_open(report) and report.due_date and report.due_date < today
    ]
