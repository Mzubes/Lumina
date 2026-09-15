from pathlib import Path

from flask import Blueprint, Response, g, jsonify, request

from database import db_session
from logs import log_action
from models import Client, FundData, Report, ReportTemplate, ReportTransition, User
from renderers import CONTENT_TYPES, RENDERERS
from report_content import resolve_report_content
from report_generator import generate_pdf
from routes.auth import require_auth
from workflow import InvalidTransition, apply_transition, requires_compliance

reports_blueprint = Blueprint('reports', __name__)

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = BACKEND_DIR / 'static' / 'reports'

REPORT_TYPES = ['factsheet', 'marketing', 'performance', 'holdings', 'pitchbook', 'meeting_pack', 'custom']

def _scoped_query():
    query = db_session.query(Report)
    user = g.current_user
    if user.get('role') == 'client':
        query = query.filter_by(client_id=user.get('client_id'), status='distributed')
    return query

def _get_scoped_report(report_id):
    return _scoped_query().filter_by(id=report_id).first()

def _save_pdf_bytes(pdf_bytes, report_id):
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    filename = REPORTS_DIR / f"report_{report_id}.pdf"
    filename.write_bytes(pdf_bytes)
    return f"/static/reports/{filename.name}"

def _serialize_report(report):
    # Every endpoint returning a single Report carries this -- the frontend's
    # workflow stepper needs it to render the Compliance step correctly
    # (done/current/skipped) after every action, not just on initial load.
    payload = report.serialize()
    payload['complianceRequired'] = requires_compliance(report)
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
    return jsonify([report.serialize() for report in reports])

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
@require_auth(roles=['admin', 'editor', 'viewer', 'compliance'])
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
    if not title or not client_id:
        return jsonify({'message': 'title and client_id are required'}), 400
    if not db_session.query(Client).filter_by(id=client_id).first():
        return jsonify({'message': 'Unknown client_id'}), 400

    template = None
    template_id = data.get('template_id')
    if template_id is not None:
        template = db_session.query(ReportTemplate).filter_by(id=template_id).first()
        if not template:
            return jsonify({'message': 'Unknown template_id'}), 400

    report = Report(
        title=title,
        client_id=client_id,
        fund_id=data.get('fund_id'),
        template_id=template.id if template else None,
        team=data.get('team') or None,
        report_type=data.get('report_type') or None,
        status='draft',
        created_by=g.current_user['user_id'],
    )
    db_session.add(report)
    db_session.commit()

    if template:
        content = resolve_report_content(report, template)
        report.file_path = _save_pdf_bytes(RENDERERS['pdf'](content), report.id)
    else:
        report.file_path = generate_pdf(data, report_id=report.id)
    db_session.commit()
    log_action(f"Report {report.id} generated from {request.remote_addr}")

    return jsonify(_serialize_report(report)), 201

@reports_blueprint.get('/api/reports/<int:report_id>/export')
@require_auth()
def export_report(report_id):
    report = _get_scoped_report(report_id)
    if not report:
        return jsonify({'message': 'Report not found'}), 404

    export_format = request.args.get('format', 'pdf')
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
        raw_format = request.args.get('raw_format', 'json')
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

def _transition_route(action, roles):
    @require_auth(roles=roles)
    def handler(report_id):
        report = _get_scoped_report(report_id)
        if not report:
            return jsonify({'message': 'Report not found'}), 404
        data = request.get_json(silent=True) or {}
        try:
            apply_transition(report, action, g.current_user['user_id'], note=data.get('note'))
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
