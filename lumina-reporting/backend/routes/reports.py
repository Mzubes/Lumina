from flask import Blueprint, request, jsonify
from report_generator import generate_pdf
from logs import log_action
from routes.auth import require_auth

reports_blueprint = Blueprint('reports', __name__)

@reports_blueprint.route('/api/generate_report', methods=['POST'])
@require_auth(roles=['admin', 'editor'])
def generate_report():
    data = request.get_json(silent=True) or {}
    report_id = generate_pdf(data)
    log_action(f"Report {report_id} generated from {request.remote_addr}")
    return jsonify({"message": "Report generated", "report_id": report_id})
