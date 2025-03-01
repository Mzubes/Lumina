from flask import Blueprint, request, jsonify
from report_generator import generate_pdf
from logs import log_action

reports_blueprint = Blueprint('reports', __name__)

@reports_blueprint.route('/api/generate_report', methods=['POST'])
def generate_report():
    data = request.json
    report_id = generate_pdf(data)
    log_action(f"Report {report_id} generated from {request.remote_addr}")
    return jsonify({"message": "Report generated", "report_id": report_id})
