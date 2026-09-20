"""Computed risk / SLA status for a client.

Deliberately computed at read time, never stored. A stored, settable status
would be a second source of truth that goes stale the moment a deadline
passes or a report moves, and it would need its own mutation UI, permission
model and audit entries. Everything below is derived from data the app
already records, so the badge can't drift from reality.

Returns both a status and the *reason* that produced it, so the UI can show
the real explanation ("Q3 Factsheet was due 12 Sep and is still open")
rather than generic copy.

Dependency direction is routes -> here; this module deliberately imports no
route modules.
"""

import datetime

from database import db_session
from models import PerformanceSnapshot, Report, ReportTransition
import workflow_engine

# A report due within this many days, still open, is worth watching.
WATCH_WINDOW_DAYS = 3
# How far back a "sent back for revisions" event still colours the client.
FLAG_LOOKBACK_DAYS = 14

ON_TRACK = 'on_track'
WATCH = 'watch'
FLAGGED = 'flagged'
SLA_BREACHED = 'sla_breached'

# Worst-first. A breached deadline outranks a rework loop, which outranks a
# soft watch signal.
PRECEDENCE = [SLA_BREACHED, FLAGGED, WATCH, ON_TRACK]


def _is_open(report):
    """Not yet delivered. A report that's already gone out can't be overdue."""
    return not workflow_engine.report_is_distributed(report)


def _sent_back_reason(report, since):
    """A report is 'sent back' when it returns to a status it already held --
    e.g. approved -> review -> draft. Detecting a revisit rather than
    comparing against a fixed status order keeps this working for
    firm-configured workflow diagrams, whose steps have no inherent
    ordering to compare against."""
    transitions = (
        db_session.query(ReportTransition)
        .filter_by(report_id=report.id)
        .order_by(ReportTransition.created_at.asc(), ReportTransition.id.asc())
        .all()
    )
    seen = set()
    for transition in transitions:
        if transition.to_status in seen and transition.created_at and transition.created_at >= since:
            return f"{report.title} was sent back to {transition.to_status}"
        if transition.from_status:
            seen.add(transition.from_status)
    return None


def _underperformance_reason(client_id):
    snapshots = (
        db_session.query(PerformanceSnapshot)
        .filter_by(client_id=client_id)
        .order_by(PerformanceSnapshot.as_of_date.desc())
        .all()
    )
    if not snapshots:
        return None
    # Prefer YTD -- the figure a relationship manager actually reports on --
    # falling back to whatever period is most recent. Same choice book.py makes.
    snapshot = next((s for s in snapshots if s.period_type == 'YTD'), snapshots[0])
    if snapshot.return_pct is None or snapshot.benchmark_return_pct is None:
        return None
    shortfall = float(snapshot.return_pct) - float(snapshot.benchmark_return_pct)
    if shortfall >= 0:
        return None
    return f"Trailing benchmark by {abs(round(shortfall * 100))}bps {snapshot.period_type}"


def client_risk(client_id, today=None):
    """-> {'status': one of the four constants, 'reason': str or None}."""
    today = today or datetime.date.today()
    reports = db_session.query(Report).filter_by(client_id=client_id).all()
    open_reports = [report for report in reports if _is_open(report)]

    overdue = [r for r in open_reports if r.due_date and r.due_date < today]
    if overdue:
        worst = min(overdue, key=lambda r: r.due_date)
        days = (today - worst.due_date).days
        return {
            'status': SLA_BREACHED,
            'reason': (
                f"{worst.title} was due {worst.due_date.isoformat()} "
                f"({days} day{'s' if days != 1 else ''} ago) and has not been delivered"
            ),
        }

    since = datetime.datetime.utcnow() - datetime.timedelta(days=FLAG_LOOKBACK_DAYS)
    for report in reports:
        reason = _sent_back_reason(report, since)
        if reason:
            return {'status': FLAGGED, 'reason': reason}

    due_soon = [r for r in open_reports if r.due_date and (r.due_date - today).days <= WATCH_WINDOW_DAYS]
    if due_soon:
        soonest = min(due_soon, key=lambda r: r.due_date)
        days = (soonest.due_date - today).days
        when = 'today' if days == 0 else f"in {days} day{'s' if days != 1 else ''}"
        return {'status': WATCH, 'reason': f"{soonest.title} is due {when} and is still open"}

    underperformance = _underperformance_reason(client_id)
    if underperformance:
        return {'status': WATCH, 'reason': underperformance}

    return {'status': ON_TRACK, 'reason': None}
