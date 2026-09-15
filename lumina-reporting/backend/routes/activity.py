from flask import Blueprint, jsonify, request

from database import db_session
from models import ComponentReview, Contact, DistributionLink, Report, ReportTransition, User
from report_content import reviewable_components
from routes.auth import require_auth

activity_blueprint = Blueprint('activity', __name__)

DEFAULT_LIMIT = 100
MAX_LIMIT = 500

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
            'created_at': link.created_at.isoformat() if link.created_at else None,
            'actor_email': actor_email,
            'report_id': report.id,
            'report_title': report.title,
            'summary': f'Created a distribution link for {contact_name}' if contact_name else 'Created an anonymous distribution link',
        }
        for link, report, actor_email, contact_name in rows
    ]

@activity_blueprint.get('/api/activity')
@require_auth(roles=['admin', 'editor', 'viewer'])
def get_activity():
    limit = request.args.get('limit', DEFAULT_LIMIT, type=int)
    limit = max(1, min(limit, MAX_LIMIT))

    # Pull up to `limit` from each source table independently, then merge and
    # trim -- guarantees the final list isn't missing recent events from a
    # quieter source just because a noisier one filled the pool first.
    events = _transition_events(limit) + _component_review_events(limit) + _distribution_link_events(limit)
    events.sort(key=lambda event: event['created_at'] or '', reverse=True)
    return jsonify(events[:limit])
