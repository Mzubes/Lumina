import csv
import datetime
import io

from flask import Blueprint, Response, jsonify, request

from database import db_session
from models import ComponentReview, Contact, DistributionLink, Report, ReportTransition, User
from report_content import reviewable_components
from routes.auth import require_auth

activity_blueprint = Blueprint('activity', __name__)

DEFAULT_LIMIT = 100
MAX_LIMIT = 500

# The action vocabulary an auditor reads by, over the three event sources.
# A workflow diagram's step names are firm-authored free text, so a
# transition's category is derived from the words the firm actually used --
# a firm that renames "Compliance" to "Risk sign-off" keeps meaningful
# categories without a migration. Anything unrecognised is 'workflow'
# rather than being forced into a category it may not belong to.
ACTION_TYPES = ['distribution', 'compliance', 'content', 'sign_off', 'created', 'rejected', 'workflow']

_REJECTION_WORDS = ('reject', 'sent back', 'request change', 'changes request', 'decline')
_COMPLIANCE_WORDS = ('complianc', 'certif', 'risk', 'legal')
_SIGN_OFF_WORDS = ('approv', 'sign-off', 'sign off', 'signoff')
_DISTRIBUTION_WORDS = ('distribut', 'deliver', 'publish', 'sent', 'release')


def _transition_action_type(from_status, to_status):
    """Categorise one workflow move by the words the firm gave its steps."""
    target = (to_status or '').lower()
    if not from_status:
        return 'created'
    # Rejection is checked before everything else: "sent back from compliance"
    # is a rejection, not a compliance event.
    if any(word in target for word in _REJECTION_WORDS):
        return 'rejected'
    if any(word in target for word in _DISTRIBUTION_WORDS):
        return 'distribution'
    if any(word in target for word in _COMPLIANCE_WORDS):
        return 'compliance'
    if any(word in target for word in _SIGN_OFF_WORDS):
        return 'sign_off'
    return 'workflow'

# Audit reference, derived rather than stored. Every event already has a
# stable identity (its own table + primary key); a stored column would need a
# migration and a backfill across three tables to say exactly the same thing,
# and could then drift out of sync. One letter per source keeps references
# unique across tables, since ids only count within their own.
REFERENCE_PREFIXES = {'transition': 'T', 'component_review': 'C', 'distribution_link': 'D'}

def reference_for(event_type, row_id):
    return f"REF-{REFERENCE_PREFIXES[event_type]}{row_id}"

def _transition_events(per_type_limit):
    rows = (
        db_session.query(ReportTransition, Report, User.email)
        .join(Report, ReportTransition.report_id == Report.id)
        .join(User, ReportTransition.actor_id == User.id)
        .order_by(ReportTransition.created_at.desc())
        .limit(per_type_limit)
        .all()
    )
    return [
        {
            'type': 'transition',
            'actionType': _transition_action_type(transition.from_status, transition.to_status),
            # What the action was performed *on*. For a workflow move that's
            # the report itself; for the other two sources it's the specific
            # component or recipient, which is the detail an auditor needs.
            'target': report.title,
            'reference': reference_for('transition', transition.id),
            'created_at': transition.created_at.isoformat() if transition.created_at else None,
            'actor_email': actor_email,
            'report_id': report.id,
            'report_title': report.title,
            'summary': f"{transition.from_status or '—'} → {transition.to_status}",
        }
        for transition, report, actor_email in rows
    ]

def _component_review_events(per_type_limit):
    rows = (
        db_session.query(ComponentReview, Report, User.email)
        .join(Report, ComponentReview.report_id == Report.id)
        .outerjoin(User, ComponentReview.reviewed_by == User.id)
        .filter(ComponentReview.reviewed_at.isnot(None))
        .order_by(ComponentReview.reviewed_at.desc())
        .limit(per_type_limit)
        .all()
    )
    events = []
    for review, report, actor_email in rows:
        components = reviewable_components(report)
        title = next((c.get('title') for c in components if c.get('id') == review.component_id), review.component_id)
        events.append({
            'type': 'component_review',
            'actionType': 'content',
            'target': title,
            'reference': reference_for('component_review', review.id),
            'created_at': review.reviewed_at.isoformat() if review.reviewed_at else None,
            'actor_email': actor_email,
            'report_id': report.id,
            'report_title': report.title,
            'summary': f'Reviewed "{title}"',
        })
    return events

def _distribution_link_events(per_type_limit):
    rows = (
        db_session.query(DistributionLink, Report, User.email, Contact.name)
        .join(Report, DistributionLink.report_id == Report.id)
        .join(User, DistributionLink.created_by == User.id)
        .outerjoin(Contact, DistributionLink.contact_id == Contact.id)
        .order_by(DistributionLink.created_at.desc())
        .limit(per_type_limit)
        .all()
    )
    return [
        {
            'type': 'distribution_link',
            'actionType': 'distribution',
            'target': contact_name or 'Anonymous recipient',
            'reference': reference_for('distribution_link', link.id),
            'created_at': link.created_at.isoformat() if link.created_at else None,
            'actor_email': actor_email,
            'report_id': report.id,
            'report_title': report.title,
            'summary': f'Created a distribution link for {contact_name}' if contact_name else 'Created an anonymous distribution link',
        }
        for link, report, actor_email, contact_name in rows
    ]

def _apply_filters(events, args):
    """Filters applied to the merged list rather than to each source query.

    Three different tables with three different date and actor columns would
    need the same predicate written three ways, and the merge already has to
    happen; filtering once afterwards keeps one definition of each filter.
    The cost is fetching rows that are then dropped, which is bounded by
    MAX_LIMIT per source.
    """
    report_id = args.get('report_id', type=int)
    if report_id:
        events = [event for event in events if event['report_id'] == report_id]

    actor = (args.get('actor') or '').strip().lower()
    if actor:
        events = [event for event in events if actor in (event['actor_email'] or '').lower()]

    action_type = args.get('action_type')
    if action_type:
        events = [event for event in events if event['actionType'] == action_type]

    # Dates are ISO-8601 strings, compared as strings: the timestamps are
    # already zero-padded ISO, so lexical order is chronological order, and
    # `until` is made inclusive of the whole day by comparing against the
    # date prefix rather than a midnight timestamp.
    since = args.get('since')
    if since:
        events = [event for event in events if (event['created_at'] or '') >= since]

    until = args.get('until')
    if until:
        events = [event for event in events if (event['created_at'] or '')[:10] <= until]

    return events


def _collect(args):
    limit = args.get('limit', DEFAULT_LIMIT, type=int)
    limit = max(1, min(limit, MAX_LIMIT))

    # Pull up to `limit` from each source table independently, then merge and
    # trim -- guarantees the final list isn't missing recent events from a
    # quieter source just because a noisier one filled the pool first.
    events = _transition_events(limit) + _component_review_events(limit) + _distribution_link_events(limit)
    events.sort(key=lambda event: event['created_at'] or '', reverse=True)
    return _apply_filters(events, args)[:limit]


@activity_blueprint.get('/api/activity')
@require_auth(roles=['admin', 'editor', 'viewer'])
def get_activity():
    return jsonify(_collect(request.args))


@activity_blueprint.get('/api/activity/export')
@require_auth(roles=['admin', 'editor', 'viewer'])
def export_activity():
    """The filtered trail as CSV, for handing to an auditor.

    Exports exactly what the screen is showing -- same query params, same
    filter code -- so an export can never disagree with the page it was
    taken from. CSV rather than the PDF pipeline: this is a record to be
    filed and re-sorted, not a rendered document, and it carries no
    template or theme.
    """
    events = _collect(request.args)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(['Reference', 'Timestamp (UTC)', 'Action', 'Actor', 'Report', 'Target', 'Detail'])
    for event in events:
        writer.writerow([
            event['reference'], event['created_at'] or '', event['actionType'],
            event['actor_email'] or '', event['report_title'], event['target'], event['summary'],
        ])

    filename = f"lumina-audit-trail-{datetime.datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.csv"
    return Response(
        buffer.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )
