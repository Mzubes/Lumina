from flask import Blueprint, jsonify, request
from report_generator import generate_pdf

reports_blueprint = Blueprint('reports', __name__)

@reports_blueprint.route('/api/generate_report', methods=['POST'])
def generate_report():
    data = request.json
    report_id = generate_pdf(data)
    return jsonify({"message": "Report generated", "report_id": report_id})
