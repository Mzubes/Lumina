import datetime
import secrets
from pathlib import Path

from flask import Blueprint, Response, g, jsonify, request

from database import db_session
from logs import log_action
from models import Client, ComponentReview, Contact, DistributionLink, FundData, Report, ReportTemplate, ReportTransition, User, WorkflowGroup
from renderers import CONTENT_TYPES, RENDERERS
from report_content import resolve_report_content, reviewable_components
from report_generator import generate_pdf
from routes.auth import require_auth
import workflow_engine
from workflow_legacy import InvalidTransition, apply_transition, requires_compliance

reports_blueprint = Blueprint('reports', __name__)

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = BACKEND_DIR / 'static' / 'reports'

REPORT_TYPES = ['factsheet', 'marketing', 'performance', 'holdings', 'pitchbook', 'meeting_pack', 'custom']

def _scoped_query():
    # Distribution visibility is no longer a SQL-level status='distributed'
    # filter here -- workflow_engine.report_is_distributed() has to inspect
    # a diagram-backed report's active step instances (which node, if any,
    # is flagged is_distribution_gate), not just compare a status string, so
    # that check happens in Python over this client's own (small) report
    # set instead. See _get_scoped_report/list_reports.
    query = db_session.query(Report)
    user = g.current_user
    if user.get('role') == 'client':
        query = query.filter_by(client_id=user.get('client_id'))
    return query

def _get_scoped_report(report_id):
    report = _scoped_query().filter_by(id=report_id).first()
    if report and g.current_user.get('role') == 'client' and not workflow_engine.report_is_distributed(report):
        return None
    return report

def _save_pdf_bytes(pdf_bytes, report_id):
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    filename = REPORTS_DIR / f"report_{report_id}.pdf"
    filename.write_bytes(pdf_bytes)
    return f"/static/reports/{filename.name}"

def _serialize_report(report):
    # Every endpoint returning a Report carries this -- the frontend's
    # workflow stepper needs it to render the Compliance step correctly
    # (done/current/skipped) after every action, not just on initial load.
    payload = report.serialize()
    payload['complianceRequired'] = requires_compliance(report)
    # Empty for a legacy (non-diagram) report -- the frontend falls back to
    # ACTIONS_BY_STATUS/the plain status string for those until it's
    # migrated to render this instead.
    if report.workflow_diagram_id is not None:
        payload['activeSteps'] = [instance.serialize() for instance in workflow_engine.active_instances(report)]
        payload['eligibleActions'] = workflow_engine.eligible_actions(
            report, g.current_user.get('role'), g.current_user.get('user_id'),
        )
    else:
        payload['activeSteps'] = []
        payload['eligibleActions'] = []
    return payload

@reports_blueprint.get('/api/reports')
@require_auth()
def list_reports():
    query = _scoped_query()
    if g.current_user.get('role') != 'client':
        status = request.args.get('status')
        if status:
            query = query.filter_by(status=status)
        client_id = request.args.get('client_id', type=int)
        if client_id:
            query = query.filter_by(client_id=client_id)
        team = request.args.get('team')
        if team:
            query = query.filter_by(team=team)
        report_type = request.args.get('report_type')
        if report_type:
            query = query.filter_by(report_type=report_type)
        asset_class = request.args.get('asset_class')
        if asset_class:
            query = query.join(FundData, Report.fund_id == FundData.id).filter(FundData.asset_class == asset_class)
        search = request.args.get('q')
        if search:
            query = query.filter(Report.title.ilike(f'%{search}%'))
    reports = query.order_by(Report.created_at.desc()).all()
    if g.current_user.get('role') == 'client':
        reports = [r for r in reports if workflow_engine.report_is_distributed(r)]
    return jsonify([_serialize_report(report) for report in reports])

@reports_blueprint.get('/api/reports/facets')
@require_auth(roles=['admin', 'editor', 'viewer'])
def get_report_facets():
    teams = [
        row[0] for row in
        db_session.query(Report.team).filter(Report.team.isnot(None)).distinct().order_by(Report.team.asc()).all()
    ]
    asset_classes = [
        row[0] for row in
        db_session.query(FundData.asset_class)
        .filter(FundData.asset_class.isnot(None)).distinct().order_by(FundData.asset_class.asc()).all()
    ]
    return jsonify({'teams': teams, 'reportTypes': REPORT_TYPES, 'assetClasses': asset_classes})

@reports_blueprint.get('/api/reports/<int:report_id>')
@require_auth()
def get_report(report_id):
    report = _get_scoped_report(report_id)
    if not report:
        return jsonify({'message': 'Report not found'}), 404
    return jsonify(_serialize_report(report))

@reports_blueprint.get('/api/reports/<int:report_id>/history')
@require_auth(roles=['admin', 'editor', 'viewer'])
def get_report_history(report_id):
    report = _get_scoped_report(report_id)
    if not report:
        return jsonify({'message': 'Report not found'}), 404
    transitions = (
        db_session.query(ReportTransition, User.email)
        .join(User, ReportTransition.actor_id == User.id)
        .filter(ReportTransition.report_id == report.id)
        .order_by(ReportTransition.created_at.asc())
        .all()
    )
    return jsonify([
        {**transition.serialize(), 'actor_email': actor_email}
        for transition, actor_email in transitions
    ])

@reports_blueprint.post('/api/reports')
@require_auth(roles=['admin', 'editor'])
def create_report():
    data = request.get_json(silent=True) or {}
    title = data.get('title')
    client_id = data.get('client_id')
    fund_id = data.get('fund_id')
    if not title or (not client_id and not fund_id):
        return jsonify({'message': 'title and (client_id or fund_id) are required'}), 400
    if client_id and not db_session.query(Client).filter_by(id=client_id).first():
        return jsonify({'message': 'Unknown client_id'}), 400
    if fund_id and not db_session.query(FundData).filter_by(id=fund_id).first():
        return jsonify({'message': 'Unknown fund_id'}), 400

    template = None
    template_id = data.get('template_id')
    if template_id is not None:
        template = db_session.query(ReportTemplate).filter_by(id=template_id).first()
        if not template:
            return jsonify({'message': 'Unknown template_id'}), 400

    report = Report(
        title=title,
        client_id=client_id or None,
        fund_id=fund_id or None,
        template_id=template.id if template else None,
        team=data.get('team') or None,
        report_type=data.get('report_type') or None,
        status='draft',
        created_by=g.current_user['user_id'],
    )
    db_session.add(report)
    db_session.commit()

    if template:
        workflow_engine.pin_to_active_diagram(report, template.id, g.current_user['user_id'])
        content = resolve_report_content(report, template)
        report.file_path = _save_pdf_bytes(RENDERERS['pdf'](content), report.id)
    else:
        report.file_path = generate_pdf(data, report_id=report.id)
    db_session.commit()
    log_action(f"Report {report.id} generated from {request.remote_addr}")

    return jsonify(_serialize_report(report)), 201

def render_export_response(report, export_format, raw_format='json'):
    """Shared by the authenticated export route and the public distribution-link
    route -- same formats, same rendering, the only difference is how the
    caller establishes it may see this report at all."""
    if export_format not in RENDERERS:
        return jsonify({'message': f"Unsupported format '{export_format}'"}), 400

    if not report.template_id:
        if export_format != 'pdf':
            return jsonify({'message': 'This report has no template; only PDF export is available'}), 400
        if not report.file_path:
            return jsonify({'message': 'No file available for this report'}), 404
        file_path = REPORTS_DIR / Path(report.file_path).name
        if not file_path.exists():
            return jsonify({'message': 'Report file is missing'}), 404
        return Response(
            file_path.read_bytes(), mimetype='application/pdf',
            headers={'Content-Disposition': f'attachment; filename="report_{report.id}.pdf"'},
        )

    template = db_session.query(ReportTemplate).filter_by(id=report.template_id).first()
    if not template:
        return jsonify({'message': 'Report template no longer exists'}), 404
    content = resolve_report_content(report, template)

    if export_format == 'raw':
        if raw_format not in ('json', 'csv'):
            return jsonify({'message': "raw_format must be 'json' or 'csv'"}), 400
        body = RENDERERS['raw'](content, raw_format=raw_format)
        mimetype = 'application/json' if raw_format == 'json' else 'text/csv'
        filename = f"report_{report.id}.{raw_format}"
    else:
        body = RENDERERS[export_format](content)
        mimetype = CONTENT_TYPES[export_format]
        filename = f"report_{report.id}.{export_format}"

    return Response(
        body, mimetype=mimetype,
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )

@reports_blueprint.get('/api/reports/<int:report_id>/export')
@require_auth()
def export_report(report_id):
    report = _get_scoped_report(report_id)
    if not report:
        return jsonify({'message': 'Report not found'}), 404
    return render_export_response(
        report, request.args.get('format', 'pdf'), request.args.get('raw_format', 'json'),
    )

# The action_label a Phase-5 auto-generated diagram's edge must carry for
# each legacy verb below to keep resolving correctly once a report has a
# workflow_diagram_id -- see _transition_route's diagram-aware branch.
_LEGACY_ACTION_LABELS = {
    'submit': 'Submit',
    'approve': 'Approve',
    'reject': 'Reject',
    'distribute': 'Distribute',
    'certify': 'Certify',
    'request_changes': 'Request Changes',
}

def _transition_route(action, roles):
    # Auth is deliberately NOT gated by `roles` at the decorator level
    # anymore: once a report has a workflow_diagram_id, who's allowed to
    # act is determined by the engine (system role + workflow group
    # membership on the report's current step), not a fixed per-verb role
    # list -- a compliance user migrated to role='editor' + "Compliance"
    # group membership must still be able to certify a migrated report
    # through this same URL. The legacy branch below re-checks `roles`
    # itself, so a non-diagram report's authorization is unchanged.
    @require_auth()
    def handler(report_id):
        report = _get_scoped_report(report_id)
        if not report:
            return jsonify({'message': 'Report not found'}), 404
        data = request.get_json(silent=True) or {}
        note = data.get('note')

        if report.workflow_diagram_id is not None:
            # Diagram-backed report: resolve this legacy verb to whichever
            # currently-eligible edge carries the matching action_label, so
            # existing per-verb call sites (ReportDetail.js) keep working
            # unmodified until they're migrated onto /transition directly.
            role = g.current_user.get('role')
            user_id = g.current_user['user_id']
            label = _LEGACY_ACTION_LABELS[action]
            match = next(
                (a for a in workflow_engine.eligible_actions(report, role, user_id) if a['label'] == label),
                None,
            )
            if match is None:
                return jsonify({'message': f"Cannot {action} a report in its current step"}), 409
            try:
                workflow_engine.apply_transition(report, match['edge_id'], user_id, note=note)
            except workflow_engine.InvalidTransition as error:
                return jsonify({'message': str(error)}), 409
            except workflow_engine.NotAuthorized as error:
                return jsonify({'message': str(error)}), 403
            return jsonify(_serialize_report(report))

        # Legacy (non-diagram) report: the original per-verb role check,
        # just moved from the decorator into the handler so it runs
        # alongside (not instead of) the diagram-aware branch above.
        if g.current_user.get('role') not in roles:
            return jsonify({'message': 'Insufficient permissions'}), 403
        try:
            apply_transition(report, action, g.current_user['user_id'], note=note)
        except InvalidTransition as error:
            return jsonify({'message': str(error)}), 409
        return jsonify(_serialize_report(report))
    return handler

reports_blueprint.add_url_rule(
    '/api/reports/<int:report_id>/submit', view_func=_transition_route('submit', ['admin', 'editor']),
    methods=['POST'], endpoint='submit_report',
)
reports_blueprint.add_url_rule(
    '/api/reports/<int:report_id>/approve', view_func=_transition_route('approve', ['admin']),
    methods=['POST'], endpoint='approve_report',
)
reports_blueprint.add_url_rule(
    '/api/reports/<int:report_id>/reject', view_func=_transition_route('reject', ['admin']),
    methods=['POST'], endpoint='reject_report',
)
reports_blueprint.add_url_rule(
    '/api/reports/<int:report_id>/distribute', view_func=_transition_route('distribute', ['admin', 'editor']),
    methods=['POST'], endpoint='distribute_report',
)
reports_blueprint.add_url_rule(
    '/api/reports/<int:report_id>/certify', view_func=_transition_route('certify', ['compliance']),
    methods=['POST'], endpoint='certify_report',
)
reports_blueprint.add_url_rule(
    '/api/reports/<int:report_id>/request-changes', view_func=_transition_route('request_changes', ['compliance']),
    methods=['POST'], endpoint='request_changes_report',
)

@reports_blueprint.get('/api/reports/<int:report_id>/eligible-actions')
@require_auth(roles=['admin', 'editor', 'viewer'])
def get_eligible_actions(report_id):
    """What the caller can currently do on this report, per its diagram --
    empty for a legacy (non-diagram) report. Powers action-button rendering
    without duplicating workflow_engine's eligibility logic in the frontend."""
    report = _get_scoped_report(report_id)
    if not report:
        return jsonify({'message': 'Report not found'}), 404
    role = g.current_user.get('role')
    return jsonify(workflow_engine.eligible_actions(report, role, g.current_user['user_id']))

@reports_blueprint.post('/api/reports/<int:report_id>/transition')
@require_auth(roles=['admin', 'editor', 'viewer'])
def transition_report(report_id):
    """The generic replacement for the six legacy verb routes above -- fires
    a specific diagram edge by id. 409s (not a valid transition) for a
    report with no diagram, same as an unknown edge_id would."""
    report = _get_scoped_report(report_id)
    if not report:
        return jsonify({'message': 'Report not found'}), 404
    data = request.get_json(silent=True) or {}
    edge_id = data.get('edge_id')
    if not edge_id:
        return jsonify({'message': 'edge_id is required'}), 400
    try:
        workflow_engine.apply_transition(report, edge_id, g.current_user['user_id'], note=data.get('note'))
    except workflow_engine.InvalidTransition as error:
        return jsonify({'message': str(error)}), 409
    except workflow_engine.NotAuthorized as error:
        return jsonify({'message': str(error)}), 403
    return jsonify(_serialize_report(report))

@reports_blueprint.get('/api/reports/<int:report_id>/distribution-links')
@require_auth(roles=['admin', 'editor', 'viewer'])
def list_distribution_links(report_id):
    report = _get_scoped_report(report_id)
    if not report:
        return jsonify({'message': 'Report not found'}), 404
    links = (
        db_session.query(DistributionLink).filter_by(report_id=report_id)
        .order_by(DistributionLink.created_at.desc()).all()
    )
    return jsonify([link.serialize() for link in links])

@reports_blueprint.post('/api/reports/<int:report_id>/distribution-links')
@require_auth(roles=['admin', 'editor'])
def create_distribution_link(report_id):
    report = _get_scoped_report(report_id)
    if not report:
        return jsonify({'message': 'Report not found'}), 404
    if not workflow_engine.report_is_distributed(report):
        return jsonify({'message': 'Only distributed reports can be shared via a link'}), 409

    data = request.get_json(silent=True) or {}
    contact_id = data.get('contact_id')
    if contact_id is not None:
        if not report.client_id:
            return jsonify({
                'message': "This report has no client; create an anonymous link instead (omit contact_id)",
            }), 400
        contact = db_session.query(Contact).filter_by(id=contact_id, client_id=report.client_id).first()
        if not contact:
            return jsonify({'message': "Unknown contact_id for this report's client"}), 400

    link = DistributionLink(
        report_id=report.id, token=secrets.token_urlsafe(32),
        contact_id=contact_id or None, created_by=g.current_user['user_id'],
    )
    db_session.add(link)
    db_session.commit()
    log_action(f"Distribution link created for report {report.id} from {request.remote_addr}")
    return jsonify(link.serialize()), 201

@reports_blueprint.post('/api/reports/<int:report_id>/distribution-links/<int:link_id>/revoke')
@require_auth(roles=['admin', 'editor'])
def revoke_distribution_link(report_id, link_id):
    report = _get_scoped_report(report_id)
    if not report:
        return jsonify({'message': 'Report not found'}), 404
    link = db_session.query(DistributionLink).filter_by(id=link_id, report_id=report_id).first()
    if not link:
        return jsonify({'message': 'Link not found'}), 404
    if link.revoked_at is None:
        link.revoked_at = datetime.datetime.utcnow()
        db_session.commit()
    return jsonify(link.serialize())

def _may_review_component(component, user_role, user_id):
    if user_role == 'admin':
        return True
    review_role = component.get('review_role')
    if review_role:
        return user_role == review_role
    review_group_id = component.get('review_group_id')
    if review_group_id is not None:
        return review_group_id in workflow_engine.group_ids_for_user(user_id)
    return False

@reports_blueprint.get('/api/reports/<int:report_id>/review-checklist')
@require_auth(roles=['admin', 'editor', 'viewer'])
def get_review_checklist(report_id):
    report = _get_scoped_report(report_id)
    if not report:
        return jsonify({'message': 'Report not found'}), 404
    components = reviewable_components(report)
    reviews_by_component = {
        review.component_id: review for review in
        db_session.query(ComponentReview).filter_by(report_id=report.id).all()
    }
    checklist = []
    for component in components:
        review = reviews_by_component.get(component['id'])
        checklist.append({
            'component_id': component['id'],
            'title': component.get('title'),
            'review_role': component.get('review_role'),
            'review_group_id': component.get('review_group_id'),
            'reviewed': review is not None,
            'reviewed_by': review.reviewed_by if review else None,
            'reviewed_at': review.reviewed_at.isoformat() if review and review.reviewed_at else None,
            'note': review.note if review else None,
        })
    return jsonify(checklist)

@reports_blueprint.post('/api/reports/<int:report_id>/components/<component_id>/review')
@require_auth(roles=['admin', 'editor', 'viewer'])
def mark_component_reviewed(report_id, component_id):
    report = _get_scoped_report(report_id)
    if not report:
        return jsonify({'message': 'Report not found'}), 404
    component = next((c for c in reviewable_components(report) if c['id'] == component_id), None)
    if not component:
        return jsonify({'message': 'Unknown or non-reviewable component_id'}), 404

    if not _may_review_component(component, g.current_user.get('role'), g.current_user['user_id']):
        return jsonify({'message': 'Not eligible to review this component'}), 403

    data = request.get_json(silent=True) or {}
    review = db_session.query(ComponentReview).filter_by(report_id=report.id, component_id=component_id).first()
    if not review:
        review = ComponentReview(report_id=report.id, component_id=component_id)
        db_session.add(review)
    review.reviewed_by = g.current_user['user_id']
    review.reviewed_at = datetime.datetime.utcnow()
    review.note = data.get('note') or None
    db_session.commit()
    return jsonify(review.serialize())

@reports_blueprint.delete('/api/reports/<int:report_id>/components/<component_id>/review')
@require_auth(roles=['admin', 'editor', 'viewer'])
def clear_component_review(report_id, component_id):
    report = _get_scoped_report(report_id)
    if not report:
        return jsonify({'message': 'Report not found'}), 404
    component = next((c for c in reviewable_components(report) if c['id'] == component_id), None)
    if not component:
        return jsonify({'message': 'Unknown or non-reviewable component_id'}), 404

    if not _may_review_component(component, g.current_user.get('role'), g.current_user['user_id']):
        return jsonify({'message': 'Not eligible to review this component'}), 403

    review = db_session.query(ComponentReview).filter_by(report_id=report.id, component_id=component_id).first()
    if not review:
        return jsonify({'message': 'Not yet reviewed'}), 404
    db_session.delete(review)
    db_session.commit()
    return '', 204

def _is_in_flight(report):
    if report.workflow_diagram_id is None:
        return report.status in ('review', 'compliance')
    return workflow_engine.is_in_flight(report)

@reports_blueprint.get('/api/reports/my-queue')
@require_auth(roles=['admin', 'editor', 'viewer'])
def get_my_queue():
    """Everything actionable by the caller, in one place, each with why it's
    there -- merges workflow actions (approvals, certifications, or any
    diagram edge the caller is eligible to fire) with pending component
    reviews. A report needing more than one thing appears once with
    multiple reasons, not once per reason.

    Diagram-backed reports are queried generically through the engine's own
    eligibility check. Legacy (non-diagram) reports keep the original fixed
    draft/review/compliance/approved/distributed queue, with the compliance
    step now keyed off membership in the 'Compliance' workflow group --
    the exact group `flask migrate-workflow-diagrams` creates for former
    role='compliance' users -- instead of a hardcoded role."""
    role = g.current_user.get('role')
    user_id = g.current_user['user_id']
    queue = {}

    def add_reason(report, **reason):
        entry = queue.setdefault(report.id, {'report': report, 'reasons': []})
        entry['reasons'].append(reason)

    for report in db_session.query(Report).filter(Report.workflow_diagram_id.isnot(None)).all():
        actions = workflow_engine.eligible_actions(report, role, user_id)
        if actions:
            labels = ', '.join(sorted({action['label'] for action in actions}))
            add_reason(report, type='action', label=f'Needs action: {labels}')

    if role == 'admin':
        for report in db_session.query(Report).filter_by(status='review', workflow_diagram_id=None).all():
            add_reason(report, type='approval', label='Needs your approval')

    compliance_group = db_session.query(WorkflowGroup).filter_by(name='Compliance').first()
    if compliance_group and compliance_group.id in workflow_engine.group_ids_for_user(user_id):
        for report in db_session.query(Report).filter_by(status='compliance', workflow_diagram_id=None).all():
            add_reason(report, type='compliance', label='Needs your compliance certification')

    in_flight = [
        report for report in db_session.query(Report).filter(Report.template_id.isnot(None)).all()
        if _is_in_flight(report)
    ]
    for report in in_flight:
        mine = [c for c in reviewable_components(report) if _may_review_component(c, role, user_id)]
        if not mine:
            continue
        reviewed_ids = {
            row.component_id for row in
            db_session.query(ComponentReview.component_id).filter_by(report_id=report.id).all()
        }
        pending = [c for c in mine if c['id'] not in reviewed_ids]
        if pending:
            count = len(pending)
            add_reason(
                report, type='component_review',
                label=f"{count} component{'s' if count != 1 else ''} {'need' if count != 1 else 'needs'} your review",
                components=[c.get('title') for c in pending],
            )

    entries = sorted(queue.values(), key=lambda entry: entry['report'].created_at or datetime.datetime.min, reverse=True)
    return jsonify([{**_serialize_report(entry['report']), 'reasons': entry['reasons']} for entry in entries])
