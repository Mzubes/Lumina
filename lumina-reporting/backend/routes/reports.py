from flask import Blueprint, g, jsonify, request

from database import db_session
from logs import log_action
from models import Client, Report, ReportTransition
from report_generator import generate_pdf
from routes.auth import require_auth
from workflow import InvalidTransition, apply_transition

reports_blueprint = Blueprint('reports', __name__)

def _scoped_query():
    query = db_session.query(Report)
    user = g.current_user
    if user.get('role') == 'client':
        query = query.filter_by(client_id=user.get('client_id'), status='distributed')
    return query

def _get_scoped_report(report_id):
    return _scoped_query().filter_by(id=report_id).first()

@reports_blueprint.get('/api/reports')
@require_auth()
def list_reports():
    query = _scoped_query()
    if g.current_user.get('role') != 'client':
        status = request.args.get('status')
        if status:
            query = query.filter_by(status=status)
    reports = query.order_by(Report.created_at.desc()).all()
    return jsonify([report.serialize() for report in reports])

@reports_blueprint.get('/api/reports/<int:report_id>')
@require_auth()
def get_report(report_id):
    report = _get_scoped_report(report_id)
    if not report:
        return jsonify({'message': 'Report not found'}), 404
    return jsonify(report.serialize())

@reports_blueprint.get('/api/reports/<int:report_id>/history')
@require_auth(roles=['admin', 'editor', 'viewer'])
def get_report_history(report_id):
    report = _get_scoped_report(report_id)
    if not report:
        return jsonify({'message': 'Report not found'}), 404
    transitions = (
        db_session.query(ReportTransition)
        .filter_by(report_id=report.id)
        .order_by(ReportTransition.created_at.asc())
        .all()
    )
    return jsonify([transition.serialize() for transition in transitions])

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

    report = Report(
        title=title,
        client_id=client_id,
        fund_id=data.get('fund_id'),
        status='draft',
        created_by=g.current_user['user_id'],
    )
    db_session.add(report)
    db_session.commit()

    report.file_path = generate_pdf(data, report_id=report.id)
    db_session.commit()
    log_action(f"Report {report.id} generated from {request.remote_addr}")

    return jsonify(report.serialize()), 201

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
        return jsonify(report.serialize())
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
