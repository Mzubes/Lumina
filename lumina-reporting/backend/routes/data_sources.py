import datetime
import json

from flask import Blueprint, g, jsonify, request

from connectors import CONNECTORS
from connectors.errors import ConnectorError
from connectors.snowflake_connector import IDENTIFIER_PATTERN
from database import db_session
from models import CONFIG_SECRET_KEYS, DataSource
from routes.auth import require_auth

data_sources_blueprint = Blueprint('data_sources', __name__)

VALID_TYPES = {'snowflake', 'api'}
SNOWFLAKE_IDENTIFIER_FIELDS = ('schema', 'holdings_table', 'performance_table', 'client_column')

def _validate_config(source_type, config):
    if not isinstance(config, dict):
        return 'config must be an object'
    if source_type == 'snowflake':
        for field in SNOWFLAKE_IDENTIFIER_FIELDS:
            value = config.get(field)
            if not value or not IDENTIFIER_PATTERN.match(value):
                return f"'{field}' must contain only letters, numbers, and underscores"
    elif source_type == 'api':
        if not config.get('base_url'):
            return "'base_url' is required"
    return None

def _get_data_source_or_404(source_id):
    return db_session.query(DataSource).filter_by(id=source_id).first()

@data_sources_blueprint.get('/api/data-sources')
@require_auth()
def list_data_sources():
    sources = db_session.query(DataSource).order_by(DataSource.created_at.desc()).all()
    return jsonify([source.serialize() for source in sources])

@data_sources_blueprint.get('/api/data-sources/<int:source_id>')
@require_auth()
def get_data_source(source_id):
    source = _get_data_source_or_404(source_id)
    if not source:
        return jsonify({'message': 'Data source not found'}), 404
    return jsonify(source.serialize())

@data_sources_blueprint.post('/api/data-sources')
@require_auth(roles=['admin'])
def create_data_source():
    data = request.get_json(silent=True) or {}
    name = data.get('name')
    source_type = data.get('type')
    config = data.get('config')
    if not name or source_type not in VALID_TYPES:
        return jsonify({'message': "name and a valid type ('snowflake' or 'api') are required"}), 400
    error = _validate_config(source_type, config)
    if error:
        return jsonify({'message': error}), 400

    source = DataSource(
        name=name,
        type=source_type,
        config=json.dumps(config),
        created_by=g.current_user['user_id'],
    )
    db_session.add(source)
    db_session.commit()
    return jsonify(source.serialize()), 201

@data_sources_blueprint.put('/api/data-sources/<int:source_id>')
@require_auth(roles=['admin'])
def update_data_source(source_id):
    source = _get_data_source_or_404(source_id)
    if not source:
        return jsonify({'message': 'Data source not found'}), 404

    data = request.get_json(silent=True) or {}
    name = data.get('name', source.name)
    source_type = data.get('type', source.type)
    if source_type not in VALID_TYPES:
        return jsonify({'message': "type must be 'snowflake' or 'api'"}), 400

    config = data.get('config')
    if config is None:
        config = source.config_dict()
    else:
        # GET redacts secrets, so an edit form re-submitting what it fetched
        # won't include them -- keep the existing secret unless a real new
        # value was provided, rather than silently wiping it on save.
        stored_config = source.config_dict()
        for secret_key in CONFIG_SECRET_KEYS:
            if not config.get(secret_key) and stored_config.get(secret_key):
                config[secret_key] = stored_config[secret_key]

    error = _validate_config(source_type, config)
    if error:
        return jsonify({'message': error}), 400

    source.name = name
    source.type = source_type
    source.config = json.dumps(config)
    db_session.commit()
    return jsonify(source.serialize())

@data_sources_blueprint.post('/api/data-sources/<int:source_id>/sync')
@require_auth(roles=['admin', 'editor'])
def sync_data_source(source_id):
    source = _get_data_source_or_404(source_id)
    if not source:
        return jsonify({'message': 'Data source not found'}), 404

    data = request.get_json(silent=True) or {}
    client_id = data.get('client_id')
    if not client_id:
        return jsonify({'message': 'client_id is required'}), 400
    fund_id = data.get('fund_id')

    connector = CONNECTORS.get(source.type)
    if not connector:
        return jsonify({'message': f"No connector registered for type '{source.type}'"}), 400

    try:
        result = connector(source, client_id=client_id, fund_id=fund_id)
    except ConnectorError as error:
        source.last_sync_status = 'error'
        source.last_sync_message = str(error)
        source.last_synced_at = datetime.datetime.utcnow()
        db_session.commit()
        return jsonify({'message': str(error)}), 502

    source.last_sync_status = 'success'
    source.last_sync_message = (
        f"Landed {result['holdings_count']} holdings, {result['performance_count']} performance rows."
    )
    source.last_synced_at = datetime.datetime.utcnow()
    db_session.commit()
    return jsonify(source.serialize())
