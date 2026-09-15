from flask import Blueprint, jsonify, request

import workflow_engine
from database import db_session
from models import DistributionLink, Report, ReportTemplate
from report_content import resolve_report_content
from routes.reports import render_export_response

public_blueprint = Blueprint('public', __name__)

def _get_report_for_token(token):
    """A link only ever grants access to the exact report it was minted for,
    and only while it's neither revoked nor the report has somehow left its
    distributed state -- there is no other authorization check on this
    entire module, so this is the one gate everything below relies on.
    workflow_engine.report_is_distributed() checks a diagram-backed report's
    current active step(s) for an is_distribution_gate node rather than
    string-matching status == 'distributed', so a firm renaming/restructuring
    its steps can't silently break this gate."""
    link = db_session.query(DistributionLink).filter_by(token=token).first()
    if not link or link.revoked_at is not None:
        return None
    report = db_session.query(Report).filter_by(id=link.report_id).first()
    if not report or not workflow_engine.report_is_distributed(report):
        return None
    return report

@public_blueprint.get('/api/public/reports/<token>')
def get_public_report(token):
    report = _get_report_for_token(token)
    if not report:
        return jsonify({'message': 'This link is invalid, revoked, or no longer active'}), 404

    if not report.template_id:
        return jsonify({
            'report_title': report.title, 'client_name': None, 'components': [],
            'header_config': {}, 'footer_config': {}, 'legacy_pdf_only': True,
        })

    template = db_session.query(ReportTemplate).filter_by(id=report.template_id).first()
    if not template:
        return jsonify({'message': 'Report template no longer exists'}), 404
    return jsonify(resolve_report_content(report, template))

@public_blueprint.get('/api/public/reports/<token>/export')
def export_public_report(token):
    report = _get_report_for_token(token)
    if not report:
        return jsonify({'message': 'This link is invalid, revoked, or no longer active'}), 404
    return render_export_response(
        report, request.args.get('format', 'pdf'), request.args.get('raw_format', 'json'),
    )
