"""Production analytics over the workflow engine's own records.

Everything here is derived from ReportStepInstance and ReportTransition,
which the engine already writes on every move -- entered_at, completed_at,
node_name and group_id are all snapshotted at the time, so these numbers
describe what actually happened rather than what the current diagram says
should happen.

Two deliberate limits, so nobody reads more into these than they carry:

- A step's duration is wall-clock time between entering and leaving the
  node. That includes nights and weekends; the app records no working
  calendar, so "2.0 days" means two elapsed days, not sixteen desk hours.
- Only *completed* visits count toward an average duration. A report still
  sitting on a step has no duration yet, and counting its age so far would
  drag every average down as work arrives. Those are surfaced separately,
  as the age of the oldest waiting item.

Dependency direction is routes -> here; this module imports no route
modules.
"""

import datetime

from sqlalchemy import func

import risk_status
import workflow_engine
from database import db_session
from models import (
    Client, Report, ReportStepInstance, ReportTransition, WorkflowGroup,
)

# A step needs at least this many completed visits before its average is
# reported as a bottleneck. One slow visit is an anecdote, not a pattern.
MIN_VISITS_FOR_AVERAGE = 2
# How many days ahead of a deadline a still-open report counts as at risk.
# Same window risk_status uses for a client-level "watch", kept in sync by
# importing it rather than restating the number.
SLA_RISK_WINDOW_DAYS = risk_status.WATCH_WINDOW_DAYS


def _hours(start, end):
    return (end - start).total_seconds() / 3600.0


def workflow_stage_progress():
    """How many reports are sitting on each workflow step right now.

    Counts active step instances, not Report.status, because a report on a
    parallel branch legitimately occupies two steps at once and a single
    status string can't say so.
    """
    rows = (
        db_session.query(ReportStepInstance.node_name, func.count(ReportStepInstance.id))
        .filter(ReportStepInstance.state == 'active')
        .group_by(ReportStepInstance.node_name)
        .order_by(func.count(ReportStepInstance.id).desc())
        .all()
    )
    return [{'label': name, 'count': count} for name, count in rows]


def slowest_steps(limit=5):
    """Average wall-clock hours per completed visit, slowest first.

    Grouped by node_name rather than node_id: a firm that renames a node
    keeps the old name on already-recorded history (that's the point of the
    snapshot), and two different diagrams that both have a "Compliance
    review" step are answering the same question about the same work.
    """
    rows = (
        db_session.query(ReportStepInstance.node_name, ReportStepInstance.entered_at, ReportStepInstance.completed_at)
        .filter(
            ReportStepInstance.state == 'done',
            ReportStepInstance.entered_at.isnot(None),
            ReportStepInstance.completed_at.isnot(None),
        )
        .all()
    )
    durations = {}
    for name, entered_at, completed_at in rows:
        durations.setdefault(name, []).append(_hours(entered_at, completed_at))

    steps = [
        {
            'label': name,
            'avgHours': round(sum(values) / len(values), 1),
            'visits': len(values),
        }
        for name, values in durations.items()
        if len(values) >= MIN_VISITS_FOR_AVERAGE
    ]
    steps.sort(key=lambda step: step['avgHours'], reverse=True)
    return steps[:limit]


def bottleneck_by_group(now=None):
    """Work currently queued on each workflow group, with the age of its
    oldest waiting item -- the question a manager actually asks ("who is
    backed up, and how long has the worst one been sitting?").

    Steps with no group are reported under their own label rather than
    dropped: unassigned work is exactly the kind that goes unnoticed.
    """
    now = now or datetime.datetime.utcnow()
    rows = (
        db_session.query(ReportStepInstance.group_id, ReportStepInstance.entered_at)
        .filter(ReportStepInstance.state == 'active')
        .all()
    )
    if not rows:
        return []

    names = dict(db_session.query(WorkflowGroup.id, WorkflowGroup.name).all())
    buckets = {}
    for group_id, entered_at in rows:
        label = names.get(group_id) or 'Unassigned'
        bucket = buckets.setdefault(label, {'label': label, 'count': 0, 'oldestDays': 0.0})
        bucket['count'] += 1
        if entered_at:
            bucket['oldestDays'] = max(bucket['oldestDays'], round(_hours(entered_at, now) / 24, 1))

    result = list(buckets.values())
    result.sort(key=lambda row: (row['count'], row['oldestDays']), reverse=True)
    return result


def team_scorecard():
    """Per-team production: how much is in flight, how much has gone out,
    and how long a delivered report took end to end.

    Turnaround is measured from the report's creation to the transition that
    delivered it, and only for reports that have actually been delivered --
    an in-flight report has no end date, and assuming "now" as its end would
    report a turnaround for work that isn't finished.
    """
    reports = db_session.query(Report).all()
    if not reports:
        return []

    delivered_at = dict(
        db_session.query(ReportTransition.report_id, func.max(ReportTransition.created_at))
        .group_by(ReportTransition.report_id)
        .all()
    )

    buckets = {}
    for report in reports:
        label = report.team or 'Unassigned'
        bucket = buckets.setdefault(label, {'label': label, 'total': 0, 'delivered': 0, 'open': 0, '_turnarounds': []})
        bucket['total'] += 1
        if workflow_engine.report_is_distributed(report):
            bucket['delivered'] += 1
            end = delivered_at.get(report.id)
            if end and report.created_at:
                bucket['_turnarounds'].append(_hours(report.created_at, end) / 24)
        else:
            bucket['open'] += 1

    result = []
    for bucket in buckets.values():
        turnarounds = bucket.pop('_turnarounds')
        bucket['avgTurnaroundDays'] = round(sum(turnarounds) / len(turnarounds), 1) if turnarounds else None
        result.append(bucket)
    result.sort(key=lambda row: row['total'], reverse=True)
    return result


def delivery_sla(today=None):
    """Firm-wide roll-up of the per-client computed risk status, so the
    Production Hub and the Internal Portal's per-client badges are always
    reading the same function.
    """
    today = today or datetime.date.today()
    counts = {status: 0 for status in risk_status.PRECEDENCE}
    for (client_id,) in db_session.query(Client.id).all():
        counts[risk_status.client_risk(client_id, today=today)['status']] += 1
    return counts


def sla_at_risk(today=None):
    """Open reports that are past their deadline or inside the warning
    window. Reports with no due_date are not counted -- an absent deadline
    is not a met one.
    """
    today = today or datetime.date.today()
    horizon = today + datetime.timedelta(days=SLA_RISK_WINDOW_DAYS)
    open_with_due_date = [
        report for report in db_session.query(Report).filter(Report.due_date.isnot(None)).all()
        if not workflow_engine.report_is_distributed(report)
    ]
    breached = [report for report in open_with_due_date if report.due_date < today]
    approaching = [report for report in open_with_due_date if today <= report.due_date <= horizon]
    return {
        'breached': len(breached),
        'approaching': len(approaching),
        'windowDays': SLA_RISK_WINDOW_DAYS,
    }


def upcoming_deadlines(limit=6, today=None):
    """Open reports with a due date, soonest first -- including ones already
    past due, since a missed deadline is the most important row on a
    deadline list, not one to hide.
    """
    today = today or datetime.date.today()
    reports = [
        report for report in
        db_session.query(Report).filter(Report.due_date.isnot(None)).order_by(Report.due_date.asc()).all()
        if not workflow_engine.report_is_distributed(report)
    ]
    return [
        {
            'reportId': report.id,
            'title': report.title,
            'dueDate': report.due_date.isoformat(),
            'daysRemaining': (report.due_date - today).days,
        }
        for report in reports[:limit]
    ]
