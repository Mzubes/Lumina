from flask import Blueprint, g, jsonify, request

import ai_assistant
from routes.auth import require_auth

ai_blueprint = Blueprint('ai', __name__)

@ai_blueprint.post('/api/ai/ask')
@require_auth(roles=['admin', 'editor', 'viewer'])
def ask():
    body = request.get_json(silent=True) or {}
    message = (body.get('message') or '').strip()
    if not message:
        return jsonify({'message': 'message is required'}), 400

    try:
        result = ai_assistant.ask(
            message, g.current_user,
            page=body.get('page'), report_id=body.get('reportId'), client_id=body.get('clientId'),
        )
    except ai_assistant.AssistantError as error:
        return jsonify({'message': str(error)}), 502

    return jsonify(result)
